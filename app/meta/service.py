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
            ingredients_from_text = await asyncio.to_thread(
                self.extractor.extract_ingredients_from_description, 
                description, 
                channel_owner_top_level_comments,
                language
            )

            if ingredients_from_text:
                self.logger.info(f"자막에서 재료 리스트 추출 결과: {meta.ingredients}")
                meta.ingredients = ingredients_from_text
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
            # 1. 영상 자체에서 메타데이터 추출 (보조 정보)
            meta_from_video = await asyncio.to_thread(
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

            # 4. 설명란과 채널 소유자 댓글에서 재료 리스트 추출 (주 정보)
            ingredients_from_text = await asyncio.to_thread(
                self.extractor.extract_ingredients_from_description, 
                description, 
                channel_owner_top_level_comments,
                language
            )

            final_ingredients = []
            if ingredients_from_text:
                self.logger.info(f"영상 인식 재료 리스트: {meta_from_video.ingredients}")
                self.logger.info(f"설명란/댓글 기반 재료 리스트: {ingredients_from_text}")

                # --- 병합 로직 시작 (설명란 우선, 영상 정보로 보완) ---
                video_ingredients_map = {ing.name: ing for ing in meta_from_video.ingredients}
                
                for text_ing in ingredients_from_text:
                    # 설명란/댓글 정보를 기준으로 하되, unit이 비어있으면 영상 정보로 채움
                    if not text_ing.unit and text_ing.name in video_ingredients_map:
                        video_ing = video_ingredients_map[text_ing.name]
                        if video_ing.unit:
                            text_ing.unit = video_ing.unit
                    final_ingredients.append(text_ing)
                # --- 병합 로직 끝 ---
                
                self.logger.info(f"병합된 최종 재료 리스트: {final_ingredients}")
            else:
                # 설명란/댓글 정보가 없으면 영상 인식 결과만 사용
                final_ingredients = meta_from_video.ingredients

            return MetaResponse(
                description=meta_from_video.description,
                ingredients=final_ingredients,
                tags=meta_from_video.tags,
                servings=meta_from_video.servings,
                cook_time=meta_from_video.cook_time
            )

        except Exception as e:
            self.logger.error(f"Failed to extract meta from video {video_id} (video mode): {str(e)}")
            raise MetaException(MetaErrorCode.META_EXTRACT_FAILED)
