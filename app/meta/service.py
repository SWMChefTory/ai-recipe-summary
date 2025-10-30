import asyncio
import logging
from typing import List

from app.caption.schema import Caption
from app.meta.client import MetaClient
from app.meta.exception import MetaErrorCode, MetaException
from app.meta.extractor import MetaExtractor
from app.meta.schema import MetaResponse


class MetaService:
    def __init__(self, client: MetaClient, extractor: MetaExtractor):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.extractor = extractor

    async def extract(self, video_id: str, captions: List[Caption]) -> MetaResponse:
        try:
            meta = await asyncio.to_thread(
                self.extractor.extract, " ".join([cap.text for cap in captions])
            )
            
            # 유튜브 영상 설명 가져오기
            description = await asyncio.to_thread(
                self.client.get_video_description, video_id
            )

            # 유튜브 영상 채널 소유자 댓글(대댓글 제외 ) 가져오기
            channel_owner_top_level_comments = await asyncio.to_thread(
                self.client.get_channel_owner_top_level_comments, video_id
            )

            # 설명란과 채널 소유자 댓글에서 재료 리스트 추출
            ingredients = await asyncio.to_thread(
                self.extractor.extract_ingredients_from_description, description, channel_owner_top_level_comments
            )

            if ingredients:
                meta.ingredients = ingredients

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