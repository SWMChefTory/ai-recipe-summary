import asyncio
import logging
from typing import List

from app.caption.schema import Caption
from app.enum import LanguageType
from app.meta.client import MetaClient
from app.meta.exception import MetaErrorCode, MetaException
from app.meta.extractor import MetaExtractor
from app.meta.schema import MetaResponse


class MetaService:
    def __init__(self, client: MetaClient, extractor: MetaExtractor):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.extractor = extractor

    async def extract(self, video_id: str, captions: List[Caption], language: LanguageType) -> MetaResponse:
        try:
            meta = await asyncio.to_thread(
                self.extractor.extract, " ".join([cap.text for cap in captions]),
                language
            )
            
            # 유튜브 영상 설명 가져오기
            description = await asyncio.to_thread(
                self.client.get_video_description, video_id
            )

            # 유튜브 영상 채널 소유자 댓글(대댓글 제외) 가져오기
            channel_owner_top_level_comments = await asyncio.to_thread(
                self.client.get_channel_owner_top_level_comments, video_id
            )

            # 설명란과 채널 소유자 댓글에서 재료 리스트 추출
            ingredients = await asyncio.to_thread(
                self.extractor.extract_ingredients_from_description, 
                description, 
                channel_owner_top_level_comments,
                language
            )

            if ingredients:
                self.logger.info(f"자막에서 재료 리스트 추출 결과: {meta.ingredients}")
                meta.ingredients = ingredients
                self.logger.info(f"설명란&댓글에서 재료 리스트 추출 결과(최종): {meta.ingredients}")

            return MetaResponse(
                description=meta.description,
                ingredients=meta.ingredients,
                tags=meta.tags,
                servings=meta.servings,
                cook_time=meta.cook_time
            )

        except Exception as e:
            self.logger.error(f"Failed to extract meta from video {video_id}: {str(e)}")
            raise MetaException(MetaErrorCode.META_EXTRACT_FAILED)

    async def extract_by_video(self, video_id: str, file_uri: str, mime_type: str, language: LanguageType) -> MetaResponse:
        try:
            # 1. 영상 자체에서 메타데이터 추출 (Gemini)
            meta = await asyncio.to_thread(
                self.extractor.extract_video,
                file_uri,
                mime_type,
                language
            )

            # 2. 유튜브 영상 설명 가져오기
            description = await asyncio.to_thread(
                self.client.get_video_description, video_id
            )

            # 3. 유튜브 영상 채널 소유자 댓글(대댓글 제외) 가져오기
            channel_owner_top_level_comments = await asyncio.to_thread(
                self.client.get_channel_owner_top_level_comments, video_id
            )

            # 4. 설명란과 채널 소유자 댓글에서 재료 리스트 추출 (보정)
            # 영상 인식보다 텍스트(설명란/댓글)가 재료 정보에 더 정확할 수 있으므로 보완
            ingredients_from_text = await asyncio.to_thread(
                self.extractor.extract_ingredients_from_description, 
                description, 
                channel_owner_top_level_comments,
                language
            )

            if ingredients_from_text:
                self.logger.info(f"영상 인식 재료 리스트: {meta.ingredients}")
                # 텍스트 기반 재료가 있으면 덮어쓰기 (또는 병합 전략 고려 가능)
                # 현재 로직은 텍스트 기반 정보를 우선시하여 덮어씀
                meta.ingredients = ingredients_from_text
                self.logger.info(f"설명란&댓글 기반 재료 리스트(최종): {meta.ingredients}")

            return MetaResponse(
                description=meta.description,
                ingredients=meta.ingredients,
                tags=meta.tags,
                servings=meta.servings,
                cook_time=meta.cook_time
            )

        except Exception as e:
            self.logger.error(f"Failed to extract meta from video {video_id} (video mode): {str(e)}")
            raise MetaException(MetaErrorCode.META_EXTRACT_FAILED)
