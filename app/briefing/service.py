import asyncio
import logging
from typing import List

from app.briefing.client import BriefingClient
from app.briefing.generator import BriefingGenerator
from app.enum import LanguageType


class BriefingService:
    FETCH_TIMEOUT_SECONDS = 45
    GENERATE_TIMEOUT_SECONDS = 45
    MAX_COMMENTS_FOR_GENERATION = 120

    def __init__(self, client: BriefingClient, generator: BriefingGenerator):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.generator = generator

    async def get(self, video_id: str, language: LanguageType) -> List[str]:
        try:
            raw_comments = await asyncio.wait_for(
                asyncio.to_thread(self.client.get_video_comments, video_id),
                timeout=self.FETCH_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            self.logger.warning(f"댓글 수집 타임아웃으로 브리핑 생성을 건너뜁니다. video_id={video_id}")
            return []

        if not raw_comments:
            return []

        generation_comments = [text for text in raw_comments if isinstance(text, str) and text.strip()]
        generation_comments = generation_comments[:self.MAX_COMMENTS_FOR_GENERATION]
        if not generation_comments:
            return []

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self.generator.generate, generation_comments, language),
                timeout=self.GENERATE_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            self.logger.warning(f"브리핑 생성 타임아웃으로 빈 응답을 반환합니다. video_id={video_id}")
            return []
