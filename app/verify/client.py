import asyncio
import json
import logging
import os
import random
import time
from typing import Dict, Any, List
from urllib.parse import urlparse

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from app.verify.exception import VerifyException, VerifyErrorCode

logger = logging.getLogger(__name__)

class VerifyClient:
    def __init__(
        self,
        region: str,
        aws_lambda_function_urls: List[str],
        aws_access_key_id: str,
        aws_secret_access_key: str,
    ):
        self.region = region
        self.aws_lambda_function_urls = aws_lambda_function_urls
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

    async def upload_video_to_gemini(self, video_id: str) -> Dict[str, Any]:
        """
        AWS Lambda Function URL (AWS_IAM 인증)을 호출하여 비디오를 Gemini(Files API)에 업로드합니다.
        Lambda는 {"video_id": ..., "action": "upload"} 요청을 받아 처리하고,
        {"file_uri": ..., "file_name": ..., "mime_type": ...} 등을 반환해야 합니다.
        """
        class _RetryableLambdaError(Exception):
            pass

        def sleep_backoff(attempt: int, base_delay: float, max_delay: float) -> None:
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            jitter = random.uniform(0, delay * 0.1)
            time.sleep(delay + jitter)

        def call_sync():
            # action="upload" 추가
            payload_json = json.dumps({"video_id": video_id, "action": "upload"}, separators=(",", ":"))

            session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region,
            )
            creds = session.get_credentials().get_frozen_credentials()

            max_attempts = int(os.getenv("VERIFY_LAMBDA_MAX_ATTEMPTS", "4"))
            base_delay = float(os.getenv("VERIFY_LAMBDA_BACKOFF_BASE", "0.5"))
            max_delay = float(os.getenv("VERIFY_LAMBDA_BACKOFF_MAX", "6.0"))

            url = None

            for attempt in range(1, max_attempts + 1):
                try:
                    if attempt > 1 and len(self.aws_lambda_function_urls) > 1 and url:
                        candidates = [u for u in self.aws_lambda_function_urls if u != url]
                        if candidates:
                            url = random.choice(candidates)
                        else:
                            url = random.choice(self.aws_lambda_function_urls)
                    else:
                        url = random.choice(self.aws_lambda_function_urls)

                    host = urlparse(url).netloc
                    region_from_url = host.split(".lambda-url.")[1].split(".on.aws")[0]

                    req = AWSRequest(
                        method="POST",
                        url=url,
                        data=payload_json,
                        headers={"Content-Type": "application/json"},
                    )
                    SigV4Auth(creds, "lambda", region_from_url).add_auth(req)

                    logger.info(f"[VerifyClient] ▶ Lambda 업로드 요청 시도 | URL={url} | region={region_from_url} | video_id={video_id}")
                    # 업로드는 시간이 걸릴 수 있으므로 timeout을 넉넉하게 설정 (예: 300초)
                    res = requests.post(url, data=payload_json, headers=dict(req.headers), timeout=300)

                    # 응답 로깅 추가
                    logger.info(f"[VerifyClient] ▶ Lambda 응답 수신 | status={res.status_code} | body={res.text[:1000]}")

                    if res.status_code >= 500:
                        raise _RetryableLambdaError(f"status={res.status_code}")

                    res.raise_for_status()
                    data = res.json()

                    # Lambda proxy 형식 또는 Function URL 직반환 형식 처리
                    if isinstance(data, dict) and "statusCode" in data:
                        status_code = data.get("statusCode")
                        if isinstance(status_code, int) and status_code >= 500:
                            raise _RetryableLambdaError(f"lambda_status={status_code}")
                        if isinstance(status_code, int) and status_code >= 400:
                            body = data.get("body", {})
                            if isinstance(body, str):
                                try:
                                    body = json.loads(body)
                                except json.JSONDecodeError:
                                    pass
                            error_msg = body.get("error", "알 수 없는 Lambda 오류")
                            raise VerifyException(VerifyErrorCode.VERIFY_FAILED, f"Lambda 클라이언트 오류: {error_msg}")

                        if "body" in data:
                            body = data["body"]
                            if isinstance(body, str):
                                try:
                                    body = json.loads(body)
                                except Exception:
                                    pass
                            return body
                    
                    # Function URL 직반환 형식
                    if isinstance(data, dict) and "file_uri" in data:
                        return data
        
                    logger.error(f"[VerifyClient] ▶ 예상치 못한 Lambda 응답 형식 | video_id={video_id} | response={data}")
                    raise VerifyException(VerifyErrorCode.VERIFY_LAMBDA_ERROR, "Lambda 응답 형식 오류 (file_uri 없음)")

                except _RetryableLambdaError as e:
                    logger.warning(f"[VerifyClient] ▶ 5xx 응답 감지 (재시도) | attempt={attempt}/{max_attempts} | err={e}")
                    if attempt == max_attempts:
                        raise VerifyException(VerifyErrorCode.VERIFY_LAMBDA_ERROR, f"Lambda 호출 재시도 실패: {e}")
                    sleep_backoff(attempt, base_delay, max_delay)
                except requests.RequestException as e:
                    status = getattr(e.response, "status_code", None)
                    if status is not None and status < 500:
                        logger.error(f"[VerifyClient] ▶ 비재시도 HTTP 오류 | status={status} | err={e}")
                        raise VerifyException(VerifyErrorCode.VERIFY_FAILED, f"Lambda HTTP 오류: {e}")
                    logger.warning(f"[VerifyClient] ▶ 요청 오류 (재시도) | attempt={attempt}/{max_attempts} | err={e}")
                    if attempt == max_attempts:
                        raise VerifyException(VerifyErrorCode.VERIFY_FAILED, f"Lambda 호출 요청 실패: {e}")
                    sleep_backoff(attempt, base_delay, max_delay)
                except Exception as e:
                    logger.error(f"[VerifyClient] ▶ Lambda 호출 중 예상치 못한 오류 | video_id={video_id} | error={e}")
                    raise VerifyException(VerifyErrorCode.VERIFY_FAILED, f"Lambda 호출 중 예상치 못한 오류: {e}")

            raise VerifyException(VerifyErrorCode.VERIFY_FAILED, "Lambda 호출 실패 (최대 재시도 횟수 초과)")
        return await asyncio.to_thread(call_sync)
