import logging
import asyncio
from typing import Dict, Any

from app.verify.generator import VerifyGenerator
from app.verify.exception import VerifyException, VerifyErrorCode

logger = logging.getLogger(__name__)

class VerifyService:
    def __init__(self, generator: VerifyGenerator):
        self.generator = generator
        self.logger = logging.getLogger(__name__)

    async def verify_recipe(self, video_id: str) -> Dict[str, Any]:
        """
        YouTube URL을 직접 Gemini에 전달하여 레시피 영상 여부를 검증합니다.
        """
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"

        try:
            self.logger.info(f"[VerifyService] ▶ 레시피 검증 시작 | video_id={video_id}")

            args = await asyncio.to_thread(self.generator.generate, youtube_url, "video/mp4")

            is_recipe = args.get("is_recipe", False)
            confidence = args.get("confidence", 0.0)
            reason = args.get("reason", "이유 없음")

            self.logger.info(f"[VerifyService] ▶ 검증 결과 | is_recipe={is_recipe} | confidence={confidence} | reason={reason}")

            if not is_recipe:
                raise VerifyException(VerifyErrorCode.VERIFY_NOT_RECIPE)

            return {
                "file_uri": youtube_url,
                "mime_type": "video/mp4"
            }

        except VerifyException:
            raise
        except Exception as e:
            self.logger.error(f"[VerifyService] ▶ 레시피 검증 중 예상치 못한 오류 발생 | video_id={video_id} | error={e}")
            raise VerifyException(VerifyErrorCode.VERIFY_FAILED)
