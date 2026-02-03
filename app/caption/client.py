import asyncio
import json
import logging
import os
import random
import time
from typing import List, Tuple
from urllib.parse import urlparse

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from app.caption.exception import CaptionErrorCode, CaptionException


class CaptionClient:
    def __init__(
        self,
        region: str,
        aws_lambda_function_urls: List[str],
        aws_access_key_id: str,
        aws_secret_access_key: str,
    ):
        self.logger = logging.getLogger(__name__)
        self.region = region
        self.aws_lambda_function_urls = aws_lambda_function_urls
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

    async def fetch_captions_from_lambda(self, video_id: str) -> Tuple[str, str]:
        """Lambda Function URL (AWS_IAM 인증) 호출"""
        class _RetryableLambdaError(Exception):
            pass

        def sleep_backoff(attempt: int, base_delay: float, max_delay: float) -> None:
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            jitter = random.uniform(0, delay * 0.1)
            time.sleep(delay + jitter)

        def call():
            # 1) payload는 문자열로 "한 번만" 직렬화 (서명=전송 동일)
            payload_json = json.dumps({"video_id": video_id}, separators=(",", ":"))

            # 4) 자격증명
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region,  # 세션 리전은 아무거나 OK
            )
            creds = session.get_credentials().get_frozen_credentials()

            max_attempts = int(os.getenv("CAPTION_LAMBDA_MAX_ATTEMPTS", "4"))
            base_delay = float(os.getenv("CAPTION_LAMBDA_BACKOFF_BASE", "0.5"))
            max_delay = float(os.getenv("CAPTION_LAMBDA_BACKOFF_MAX", "6.0"))

            url = None

            for attempt in range(1, max_attempts + 1):
                try:
                    # 2) 재시도마다 URL 랜덤 선택(직전 URL은 피함)
                    if attempt > 1 and len(self.aws_lambda_function_urls) > 1 and url:
                        candidates = [u for u in self.aws_lambda_function_urls if u != url]
                        if candidates:
                            url = random.choice(candidates)
                        else:
                            url = random.choice(self.aws_lambda_function_urls)
                    else:
                        url = random.choice(self.aws_lambda_function_urls)

                    # 3) URL에서 region 파싱 (ex: id.lambda-url.ap-northeast-1.on.aws)
                    host = urlparse(url).netloc
                    # host 분해: '<id>.lambda-url.<region>.on.aws'
                    region_from_url = host.split(".lambda-url.")[1].split(".on.aws")[0]

                    # 5) 같은 바디로 서명 + 같은 바디로 전송
                    req = AWSRequest(
                        method="POST",
                        url=url,
                        data=payload_json,
                        headers={"Content-Type": "application/json"},
                    )
                    SigV4Auth(creds, "lambda", region_from_url).add_auth(req)

                    self.logger.info(f"Lambda region: {region_from_url}")

                    res = requests.post(url, data=payload_json, headers=dict(req.headers), timeout=90)

                    if res.status_code >= 500:
                        raise _RetryableLambdaError(f"status={res.status_code}")

                    res.raise_for_status()
                    data = res.json()

                    if isinstance(data, dict) and "statusCode" in data:
                        status_code = data.get("statusCode")
                        if isinstance(status_code, int) and status_code >= 500:
                            raise _RetryableLambdaError(f"lambda_status={status_code}")

                    # Lambda proxy 형식
                    if isinstance(data, dict) and "body" in data:
                        body = data["body"]
                        if isinstance(body, str):
                            try:
                                body = json.loads(body)
                            except Exception:
                                pass
                        return body["captions"], body["lang_code"]
        
                    # Function URL 직반환 형식
                    if isinstance(data, dict) and "captions" in data and "lang_code" in data:
                        return data["captions"], data["lang_code"]
        
                    self.logger.error(f"Unexpected Lambda response: {data}")
                    raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)

                except _RetryableLambdaError as e:
                    self.logger.warning(f"[Lambda Retry] 5xx 응답 감지. attempt={attempt}/{max_attempts} err={e}")
                    if attempt == max_attempts:
                        raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)
                    sleep_backoff(attempt, base_delay, max_delay)
                except requests.RequestException as e:
                    status = getattr(e.response, "status_code", None)
                    if status is not None and status < 500:
                        self.logger.error(f"[Lambda Error] 비재시도 HTTP 오류. status={status} err={e}")
                        raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)
                    self.logger.warning(f"[Lambda Retry] 요청 오류. attempt={attempt}/{max_attempts} err={e}")
                    if attempt == max_attempts:
                        raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)
                    sleep_backoff(attempt, base_delay, max_delay)

        return await asyncio.to_thread(call)
