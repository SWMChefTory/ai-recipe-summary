import asyncio
import html
import logging
import re
from typing import List

import emoji

from app.briefing.client import BriefingClient
from app.briefing.comment_classifier import CommentClassifier
from app.briefing.generator import BriefingGenerator


class BriefingService:
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

    async def get(self, video_id: str) -> List[str]:
        # 1) 댓글 추출
        raw_comments = await asyncio.to_thread(
            self.client.get_video_comments, video_id
        )

        if not raw_comments:
            return []

        # 2) 댓글 정리
        cleaned_comments = [
            c for c in (self.__clean_comment(x) for x in raw_comments) 
            if c and 6 <= len(c) <= 300
        ]
        self.logger.info(f"태그 및 길이 필터링 후 남은 댓글: {len(cleaned_comments)}개")

        # 3) 레시피 관련 댓글만 필터링
        filtered_comments = await asyncio.to_thread(
            self.classifier.predict, cleaned_comments
        )
        self.logger.info(f"레시피 관련 댓글 필터링 후 남은 댓글: {len(filtered_comments)}개")

        if len(filtered_comments) < 8:
            self.logger.info(f"레시피 관련 댓글이 충분하지 않아서 브리핑을 생성하지 않습니다.")
            return []

        # 4) 브리핑 생성
        return await asyncio.to_thread(
            self.generator.generate, filtered_comments
        )
