import asyncio
import logging
import os
from typing import List, Tuple

import pysrt

from app.caption.client import CaptionClient
from app.caption.exception import CaptionErrorCode, CaptionException
from app.caption.recipe_validator import CaptionRecipeValidator
from app.caption.schema import Caption


class CaptionService:
    def __init__(self, client: CaptionClient, recipe_validator: CaptionRecipeValidator):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.recipe_validator = recipe_validator

    def __srt_str_to_captions(self, raw_captions: str) -> List[Caption]:
        try:
            srt_captions = pysrt.from_string(raw_captions)

            captions: List[Caption] = []
            for srt_cap in srt_captions:
                start = srt_cap.start.ordinal / 1000.0
                end = srt_cap.end.ordinal / 1000.0
                text = (srt_cap.text or "").strip()
                if text:
                    captions.append(Caption(start=start, end=end, text=text))

            return captions
        except Exception as e:
            self.logger.error(f"SRT 문자열을 Caption 객체로 변환 중 오류가 발생했습니다. error={e}")
            raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)


    async def get_captions_with_lang_code(self, video_id: str) -> Tuple[List[Caption], str]:
        # 1) 원본 자막 다운로드
        raw_captions, lang_code = await asyncio.to_thread(
            self.client.get_captions_with_lang_code, video_id
        )

        # 2) 원본 자막을 Caption 객체 변환
        captions = self.__srt_str_to_captions(raw_captions)

        # 3) 레시피 관련 자막인지 검증
        captions_text = " ".join(seg.text for seg in captions)
        await asyncio.to_thread(
          self.recipe_validator.validate, captions_text, lang_code, video_id
        )

        return captions, lang_code