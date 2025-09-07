import asyncio
import logging
from typing import List

from app.caption.schema import CaptionSegment
from app.ingredient.client import IngredientClient
from app.ingredient.exception import IngredientErrorCode, IngredientException
from app.ingredient.extractor import IngredientExtractor
from app.ingredient.schema import Ingredient


class IngredientService:
    def __init__(self, client: IngredientClient, extractor: IngredientExtractor):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.extractor = extractor

    async def extract(self, video_id: str, captions: List[CaptionSegment], lang_code: str) -> List[Ingredient]:
        try:
            # 유튜브 영상 설명 가져오기
            description = await asyncio.to_thread(
                self.client.get_video_description, video_id
            )

            # 설명란에서 재료 리스트 추출
            ingredient_list = await asyncio.to_thread(
                self.extractor.extract_from_description, description
            )

            if ingredient_list:
                return [
                    Ingredient(
                        name=ingredient["name"],
                        amount=ingredient.get("amount"),
                        unit=ingredient.get("unit")
                    )
                    for ingredient in ingredient_list
                ]

            # 자막에서 재료 리스트 추출
            ingredient_list = await asyncio.to_thread(
                self.extractor.extract_from_captions, " ".join([cap.text for cap in captions]), lang_code
            )

            if ingredient_list:
                return [
                    Ingredient(
                        name=ingredient["name"],
                        amount=ingredient.get("amount"),
                        unit=ingredient.get("unit")
                    )
                    for ingredient in ingredient_list
                ]                

            raise IngredientException(IngredientErrorCode.INGREDIENT_NOT_FOUND)
        
        except IngredientException:
            raise

        except Exception as e:
            self.logger.error(f"Failed to extract ingredients from video {video_id}: {str(e)}")
            raise IngredientException(IngredientErrorCode.INGREDIENT_EXTRACT_FAILED)