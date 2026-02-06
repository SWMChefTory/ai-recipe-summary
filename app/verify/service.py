import logging
import asyncio
from typing import Dict, Any
from urllib.parse import urlparse

from google import genai

from app.verify.client import VerifyClient
from app.verify.generator import VerifyGenerator
from app.verify.exception import VerifyException, VerifyErrorCode

logger = logging.getLogger(__name__)

class VerifyService:
    def __init__(
        self,
        client: VerifyClient,
        generator: VerifyGenerator,
        genai_client: genai.Client,
    ):
        self.client = client
        self.generator = generator
        self.genai_client = genai_client
        self.logger = logging.getLogger(__name__)

    async def verify_recipe(self, video_id: str) -> Dict[str, Any]:
        """
        1) VerifyClient를 통해 비디오를 Gemini에 업로드합니다.
        2) 업로드된 비디오(file_uri)를 사용하여 Gemini API로 레시피 여부를 검증합니다.
        """
        try:
            # 1. 비디오 업로드 (Lambda 호출)
            self.logger.info(f"[VerifyService] ▶ 비디오 업로드 시작 | video_id={video_id}")
            try:
                upload_result = await self.client.upload_video_to_gemini(video_id)
            except Exception as e:
                self.logger.error(f"[VerifyService] ▶ 비디오 업로드 실패 | video_id={video_id} | error={e}")
                raise VerifyException(VerifyErrorCode.VERIFY_LAMBDA_ERROR)
            
            file_uri = upload_result.get("file_uri")
            file_name = upload_result.get("file_name")
            mime_type = upload_result.get("mime_type", "video/mp4")

            if not file_uri:
                self.logger.error(f"[VerifyService] ▶ 비디오 업로드 실패 (file_uri 없음) | video_id={video_id}")
                raise VerifyException(VerifyErrorCode.VERIFY_LAMBDA_ERROR)

            self.logger.info(f"[VerifyService] ▶ 비디오 업로드 성공 | file_uri={file_uri}")

            # 1.5 파일 상태 대기 (ACTIVE 될 때까지)
            if file_name:
                await self._wait_for_file_active(file_name)
            else:
                self.logger.warning(f"[VerifyService] ▶ file_name이 없어 상태 확인을 건너뜁니다. | video_id={video_id}")

            # 2. Gemini API로 레시피 검증 (VerifyGenerator 사용)
            try:
                args = await asyncio.to_thread(self.generator.generate, file_uri, mime_type)
            except Exception as e:
                self.logger.error(f"[VerifyService] ▶ Gemini 검증 실패 | video_id={video_id} | error={e}")
                raise VerifyException(VerifyErrorCode.VERIFY_FAILED)
            
            is_recipe = args.get("is_recipe", False)
            confidence = args.get("confidence", 0.0)
            reason = args.get("reason", "이유 없음")

            # 로깅
            self.logger.info(f"[VerifyService] ▶ 검증 결과 | is_recipe={is_recipe} | confidence={confidence} | reason={reason} | file_uri={file_uri}")

            if not is_recipe:
                # 레시피가 아님
                await self.delete_file_by_url(file_uri)
                raise VerifyException(VerifyErrorCode.VERIFY_NOT_RECIPE)

            return {
                "file_uri": file_uri,
                "mime_type": mime_type
            }

        except VerifyException:
            raise
        except Exception as e:
            self.logger.error(f"[VerifyService] ▶ 레시피 검증 중 예상치 못한 오류 발생 | video_id={video_id} | error={e}")
            raise VerifyException(VerifyErrorCode.VERIFY_FAILED)

    async def _wait_for_file_active(self, file_name: str):
        """파일이 ACTIVE 상태가 될 때까지 대기합니다."""
        self.logger.info(f"[VerifyService] ▶ 파일 처리 대기 시작 | file_name={file_name}")
        
        for _ in range(150): # 최대 150번 시도 (약 5분)
            try:
                # google.genai 라이브러리의 동기 호출을 별도 스레드에서 실행하여 이벤트 루프 차단 방지
                file_obj = await asyncio.to_thread(self.genai_client.files.get, name=file_name)
                
                if file_obj.state.name == "ACTIVE":
                    self.logger.info(f"[VerifyService] ▶ 파일 처리 완료 (ACTIVE) | file_name={file_name}")
                    return
                
                if file_obj.state.name == "FAILED":
                    raise VerifyException(VerifyErrorCode.VERIFY_FAILED) # 파일 처리 실패

                self.logger.info(f"[VerifyService] ▶ 파일 처리 중... ({file_obj.state.name}) | file_name={file_name}")
                await asyncio.sleep(2)

            except Exception as e:
                self.logger.warning(f"[VerifyService] ▶ 파일 상태 확인 중 오류 (재시도) | error={e}")
                await asyncio.sleep(2)
        
        self.logger.error(f"[VerifyService] ▶ 파일 처리 시간 초과 | file_name={file_name}")
        raise VerifyException(VerifyErrorCode.VERIFY_FAILED) # 시간 초과

    async def delete_file_by_url(self, file_uri: str):
        """Gemini File URI를 파싱하여 파일을 삭제합니다."""
        try:
            # URI 예시: https://generativelanguage.googleapis.com/v1beta/files/abc123xyz
            # 경로의 마지막 부분이 file_name (files/abc123xyz)
            parsed_url = urlparse(file_uri)
            path_parts = parsed_url.path.split('/')
            
            # "files" 키워드 이후의 경로를 추출
            if "files" in path_parts:
                idx = path_parts.index("files")
                file_name = "/".join(path_parts[idx:])
                
                # 동기 삭제 호출을 별도 스레드에서 실행
                await asyncio.to_thread(self.genai_client.files.delete, name=file_name)
                self.logger.info(f"[VerifyService] ▶ 파일 삭제 성공 | file_name={file_name}")
            else:
                self.logger.warning(f"[VerifyService] ▶ 유효하지 않은 Gemini File URI 형식입니다. | file_uri={file_uri}")
                
        except Exception as e:
            self.logger.warning(f"[VerifyService] ▶ 파일 삭제 실패 (무시 가능) | file_uri={file_uri} | error={e}")
