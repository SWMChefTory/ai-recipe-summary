import asyncio
import logging
from typing import List, Tuple

from app.caption.client import CaptionClient
from app.caption.recipe_validator import CaptionRecipeValidator
from app.caption.schema import CaptionSegment


class CaptionService:
    def __init__(self, client: CaptionClient, recipe_validator: CaptionRecipeValidator):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.recipe_validator = recipe_validator

    async def extract(self, video_id: str) -> Tuple[List[CaptionSegment], str]:
        caption_lang, caption_type = await asyncio.to_thread(
            self.client.get_captions_lang_with_ytdlp, video_id
        )

        captions = await asyncio.to_thread(
            self.client.extract_captions_with_ytdlp, video_id, caption_type, caption_lang
        )
        
        captions_text = " ".join(seg.text for seg in captions)

        await self.recipe_validator.validate(captions_text, caption_lang)

        if caption_lang.endswith("-orig"):
            caption_lang = caption_lang[:-5]

        return captions, caption_lang