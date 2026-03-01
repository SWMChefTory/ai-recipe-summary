import asyncio
import json
import logging
import os
import random
import time
from typing import Dict, Any, List

import requests

from app.verify.exception import VerifyException, VerifyErrorCode

logger = logging.getLogger(__name__)

class VerifyClient:
    def __init__(
        self,
        upload_service_urls: List[str],
        request_timeout_seconds: int = 300,
    ):
        self.upload_service_urls = [url.strip() for url in upload_service_urls if url and url.strip()]
        self.request_timeout_seconds = request_timeout_seconds

    async def upload_video_to_gemini(self, video_id: str) -> Dict[str, Any]:
        """
        Cloud Run 업로드 서비스를 호출하여 비디오를 Gemini(Files API)에 업로드합니다.
        서비스는 {"video_id": ..., "action": "upload"} 요청을 받아 처리하고,
        {"file_uri": ..., "file_name": ..., "mime_type": ...} 등을 반환해야 합니다.
        """
        if not self.upload_service_urls:
            raise VerifyException(VerifyErrorCode.VERIFY_UPLOAD_ERROR, "업로드 서비스 URL이 비어 있습니다.")

        class _RetryableUploadError(Exception):
            pass

        def sleep_backoff(attempt: int, base_delay: float, max_delay: float) -> None:
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            jitter = random.uniform(0, delay * 0.1)
            time.sleep(delay + jitter)

        def call_sync():
            payload_json = json.dumps({"video_id": video_id, "action": "upload"}, separators=(",", ":"))

            max_attempts = int(os.getenv("VERIFY_UPLOAD_MAX_ATTEMPTS", "4"))
            base_delay = float(os.getenv("VERIFY_UPLOAD_BACKOFF_BASE", "0.5"))
            max_delay = float(os.getenv("VERIFY_UPLOAD_BACKOFF_MAX", "6.0"))

            url = None

            for attempt in range(1, max_attempts + 1):
                try:
                    if attempt > 1 and len(self.upload_service_urls) > 1 and url:
                        candidates = [u for u in self.upload_service_urls if u != url]
                        if candidates:
                            url = random.choice(candidates)
                        else:
                            url = random.choice(self.upload_service_urls)
                    else:
                        url = random.choice(self.upload_service_urls)

                    logger.info(f"[VerifyClient] ▶ 업로드 요청 시도 | URL={url} | video_id={video_id}")
                    res = requests.post(
                        url,
                        data=payload_json,
                        headers={"Content-Type": "application/json"},
                        timeout=self.request_timeout_seconds,
                    )

                    logger.info(f"[VerifyClient] ▶ 업로드 응답 수신 | status={res.status_code} | body={res.text[:1000]}")

                    if res.status_code >= 500:
                        raise _RetryableUploadError(f"status={res.status_code}")

                    res.raise_for_status()
                    data = res.json()

                    # 일부 서비스는 proxy 호환 포맷(statusCode/body)을 반환할 수 있으므로 호환 처리
                    if isinstance(data, dict) and "statusCode" in data:
                        status_code = data.get("statusCode")
                        if isinstance(status_code, int) and status_code >= 500:
                            raise _RetryableUploadError(f"upload_status={status_code}")
                        if isinstance(status_code, int) and status_code >= 400:
                            body = data.get("body", {})
                            if isinstance(body, str):
                                try:
                                    body = json.loads(body)
                                except json.JSONDecodeError:
                                    pass
                            error_msg = body.get("error", "알 수 없는 업로드 서비스 오류")
                            raise VerifyException(VerifyErrorCode.VERIFY_FAILED, f"업로드 서비스 클라이언트 오류: {error_msg}")

                        if "body" in data:
                            body = data["body"]
                            if isinstance(body, str):
                                try:
                                    body = json.loads(body)
                                except Exception:
                                    pass
                            if isinstance(body, dict) and "file_uri" in body:
                                return body

                    if isinstance(data, dict) and "file_uri" in data:
                        return data

                    logger.error(f"[VerifyClient] ▶ 예상치 못한 업로드 응답 형식 | video_id={video_id} | response={data}")
                    raise VerifyException(VerifyErrorCode.VERIFY_UPLOAD_ERROR, "업로드 응답 형식 오류 (file_uri 없음)")

                except _RetryableUploadError as e:
                    logger.warning(f"[VerifyClient] ▶ 5xx 응답 감지 (재시도) | attempt={attempt}/{max_attempts} | err={e}")
                    if attempt == max_attempts:
                        raise VerifyException(VerifyErrorCode.VERIFY_UPLOAD_ERROR, f"업로드 호출 재시도 실패: {e}")
                    sleep_backoff(attempt, base_delay, max_delay)
                except requests.RequestException as e:
                    status = getattr(e.response, "status_code", None)
                    if status is not None and status < 500:
                        logger.error(f"[VerifyClient] ▶ 비재시도 HTTP 오류 | status={status} | err={e}")
                        raise VerifyException(VerifyErrorCode.VERIFY_FAILED, f"업로드 HTTP 오류: {e}")
                    logger.warning(f"[VerifyClient] ▶ 요청 오류 (재시도) | attempt={attempt}/{max_attempts} | err={e}")
                    if attempt == max_attempts:
                        raise VerifyException(VerifyErrorCode.VERIFY_FAILED, f"업로드 호출 요청 실패: {e}")
                    sleep_backoff(attempt, base_delay, max_delay)
                except Exception as e:
                    logger.error(f"[VerifyClient] ▶ 업로드 호출 중 예상치 못한 오류 | video_id={video_id} | error={e}")
                    raise VerifyException(VerifyErrorCode.VERIFY_FAILED, f"업로드 호출 중 예상치 못한 오류: {e}")

            raise VerifyException(VerifyErrorCode.VERIFY_FAILED, "업로드 호출 실패 (최대 재시도 횟수 초과)")
        return await asyncio.to_thread(call_sync)
