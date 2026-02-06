import asyncio
import html
import logging
import re
from typing import List

import emoji

from app.briefing.client import BriefingClient
from app.briefing.comment_classifier import CommentClassifier
from app.briefing.generator import BriefingGenerator
from app.enum import LanguageType


class BriefingService:
    FETCH_TIMEOUT_SECONDS = 45
    CLASSIFY_TIMEOUT_SECONDS = 45
    GENERATE_TIMEOUT_SECONDS = 45
    MAX_COMMENTS_FOR_CLASSIFICATION = 200
    MAX_COMMENTS_FOR_GENERATION = 120

    def __init__(self, client: BriefingClient, generator: BriefingGenerator, classifier: CommentClassifier):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.generator = generator
        self.classifier = classifier

    @staticmethod
    def __clean_comment(text: str) -> str:
        if not isinstance(text, str):
            return ""
        
        # 1) 태그 제거: <br>, <a ...>...</a> 등
        text = re.sub(r"<[^>]+>", "", text)
        
        # 2) 엔티티 디코딩: &lt; -> <, &#128514; -> 😂
        text = html.unescape(text)
        
        # 3) 이모지 제거: 이모지를 찾아서 ""(빈 문자열)로 바꿔줍니다.
        text = emoji.replace_emoji(text, replace="")
        
        # 4) 공백 정리
        text = re.sub(r"\s+", " ", text).strip()
        
        return text

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

        # 2) 댓글 정리
        cleaned_comments = [
            c for c in (self.__clean_comment(x) for x in raw_comments) 
            if c and 6 <= len(c) <= 300
        ]
        if len(cleaned_comments) > self.MAX_COMMENTS_FOR_CLASSIFICATION:
            cleaned_comments = cleaned_comments[:self.MAX_COMMENTS_FOR_CLASSIFICATION]
        self.logger.info(f"태그 및 길이 필터링 후 남은 댓글: {len(cleaned_comments)}개")

        try:
            filtered_comments = await asyncio.wait_for(
                asyncio.to_thread(self.classifier.predict, cleaned_comments),
                timeout=self.CLASSIFY_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            self.logger.warning(f"댓글 분류 타임아웃으로 브리핑 생성을 건너뜁니다. video_id={video_id}")
            return []

        self.logger.info(f"레시피 관련 댓글 필터링 후 남은 댓글: {len(filtered_comments)}개")

        if len(filtered_comments) < 8:
            self.logger.info(f"레시피 관련 댓글이 충분하지 않아서 브리핑을 생성하지 않습니다.")
            return []

        generation_comments = filtered_comments[:self.MAX_COMMENTS_FOR_GENERATION]

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self.generator.generate, generation_comments, language),
                timeout=self.GENERATE_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            self.logger.warning(f"브리핑 생성 타임아웃으로 빈 응답을 반환합니다. video_id={video_id}")
            return []
