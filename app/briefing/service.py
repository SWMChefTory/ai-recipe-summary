import asyncio
import html
import logging
import re

from app.briefing.client import BriefingClient
from app.briefing.generator import BriefingGenerator
from app.briefing.schema import BriefingResponse


class BriefingService:
    def __init__(self, client: BriefingClient, generator: BriefingGenerator):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.generator = generator

    @staticmethod
    def _clean_comment(text: str) -> str:
        if not isinstance(text, str):
            return ""
        # 1) 태그 제거: <br>, <a ...>...</a> 등
        text = re.sub(r"<[^>]+>", "", text)
        # 2) 엔티티 디코딩: &lt; &gt; &#39; 등
        text = html.unescape(text)
        # 3) 공백 정리
        text = re.sub(r"\s+", " ", text).strip()
        return text

    async def get(self, video_id: str) -> BriefingResponse:
        # 1) 댓글 추출
        raw_comments = await asyncio.to_thread(
            self.client.get_video_comments, video_id
        )

        # 2) 댓글 정리
        cleaned_comments = [
            c for c in (self._clean_comment(x) for x in raw_comments) if c
        ]

        # 3) 댓글 필터링
        filtered_comments = await asyncio.to_thread(
            self.generator.filter_comments, cleaned_comments
        )

        # 4) 브리핑 생성
        return await asyncio.to_thread(
            self.generator.generate, filtered_comments
        )
