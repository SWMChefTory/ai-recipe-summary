import json
from typing import List, Optional, Tuple

from app.models.recipe import Ingredient, RecipeSummary
from app.models.summary import VideoType
from app.services.base import BaseService
from app.services.captions import CaptionService
from app.services.ingredients import IngredientsService
from app.services.summaries import SummaryService
from app.services.youtube import YouTubeService


class RecipeService(BaseService):
    """레시피 생성을 위한 통합 서비스"""

    def __init__(
        self,
        youtube_service: YouTubeService,
        caption_service: CaptionService,
        ingredients_service: IngredientsService,
        summary_service: SummaryService,
    ):
        super().__init__()
        self.youtube_service = youtube_service
        self.caption_service = caption_service
        self.ingredients_service = ingredients_service
        self.summary_service = summary_service

    async def extract_captions(self, video_id: str, video_type: VideoType) -> Optional[Tuple[List[dict], str]]:
        """영상에서 자막 추출"""
        captions = None
        lang_code = None

        if video_type == VideoType.youtube:
            result = self.youtube_service.get_subtitles_and_lang_code(video_id)
            if result is not None:
                captions, lang_code = result

        if captions is None or lang_code is None:
            self.logger.warning(f"자막을 찾을 수 없습니다: video_id={video_id}")
            return None

        normalized_captions = self.caption_service.normalize_captions(captions)
        return normalized_captions, lang_code

    async def extract_ingredients(self, captions: List[dict], description: str = "") -> List[Ingredient]:
        """자막과 설명에서 재료 추출"""
        return self.ingredients_service.extract_ingredients(captions, description)

    async def create_summary(self, captions: List[dict], description: str) -> Optional[RecipeSummary]:
        """레시피 요약 생성"""
        try:
            # 재료 추출
            ingredients = await self.extract_ingredients(captions, description)

            # 요약 생성
            summary_result = self.summary_service.summarize(captions, description)
            
            # JSON 파싱해서 RecipeSummary 객체 생성
            summary_data = json.loads(summary_result)

            recipe = RecipeSummary(
                title=summary_data.get("title", ""),
                summary=summary_data.get("summary", ""),
                total_time_sec=summary_data.get("total_time_sec"),
                ingredients=ingredients,
                steps=summary_data.get("steps", [])
            )

            return recipe

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 파싱 오류: {e}")
            return None
        except Exception as e:
            self.logger.exception(f"요약 생성 중 오류: {e}")
            return None

    async def create_full_recipe(self, video_id: str, video_type: VideoType) -> Optional[dict]:
        """전체 레시피 생성 워크플로우"""
        try:
            # 1. 자막 추출
            caption_result = await self.extract_captions(video_id, video_type)
            if caption_result is None:
                return None

            normalized_captions, lang_code = caption_result

            # 2. 영상 설명 가져오기
            description = ""
            if video_type == VideoType.youtube:
                description = self.youtube_service.get_video_description(video_id)

            # 3. 레시피 요약 생성
            recipe = await self.create_summary(normalized_captions, description)
            if recipe is None:
                return None

            # 4. 결과 반환
            return {
                "video_id": video_id,
                "lang_code": lang_code,
                "captions": normalized_captions,
                "description": description,
                "recipe": recipe
            }

        except Exception as e:
            self.logger.exception(f"전체 레시피 생성 중 오류: {e}")
            return None

    async def create_recipe_with_custom_ingredients(
        self, video_id: str, video_type: VideoType, custom_ingredients: List[Ingredient]
    ) -> Optional[RecipeSummary]:
        """사용자 지정 재료로 레시피 생성"""
        try:
            # 1. 자막 추출
            caption_result = await self.extract_captions(video_id, video_type)
            if caption_result is None:
                return None

            normalized_captions, _ = caption_result

            # 2. 영상 설명 가져오기
            description = ""
            if video_type == VideoType.youtube:
                description = self.youtube_service.get_video_description(video_id)

            # 3. 요약 생성 (재료는 사용자 지정)
            summary_result = self.summary_service.summarize(normalized_captions, description)
            summary_data = json.loads(summary_result)

            recipe = RecipeSummary(
                title=summary_data.get("title", ""),
                summary=summary_data.get("summary", ""),
                total_time_sec=summary_data.get("total_time_sec"),
                ingredients=custom_ingredients,  # 사용자 지정 재료 사용
                steps=summary_data.get("steps", [])
            )

            return recipe

        except Exception as e:
            self.logger.exception(f"사용자 지정 재료 레시피 생성 중 오류: {e}")
            return None 