from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException

from app.container import Container
from app.models import *
from app.models.summary import VideoType
from app.services.captions import CaptionService
from app.services.ingredients import IngredientsService
from app.services.recipe import RecipeService
from app.services.summaries import SummaryService
from app.services.youtube import YouTubeService

router = APIRouter()


@router.post("/captions", response_model=CaptionResponse)
@inject
async def extract_captions(
    req: CaptionRequest,
    youtube_service: YouTubeService = Depends(Provide[Container.youtube_service]),
    caption_service: CaptionService = Depends(Provide[Container.caption_service]),
):
    """자막 추출 API"""
    try:
        video_id = req.video_id
        video_type = req.video_type

        captions = None
        lang_code = None
        
        if video_type == VideoType.youtube:
            result = youtube_service.get_subtitles_and_lang_code(video_id)
            if result is not None:
                captions, lang_code = result

        if captions is None or lang_code is None:
            raise HTTPException(status_code=404, detail="Captions not found")

        normalized_captions = caption_service.normalize_captions(captions)
        
        return CaptionResponse(
            video_id=video_id,
            lang_code=lang_code,
            captions=normalized_captions
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"자막 추출 중 오류: {str(e)}")


@router.post("/ingredients", response_model=IngredientsResponse)
@inject
async def extract_ingredients_api(
    req: IngredientsRequest,
    ingredients_service: IngredientsService = Depends(Provide[Container.ingredients_service]),
):
    """재료 추출 API"""
    try:
        ingredients = ingredients_service.extract_ingredients(req.captions, req.description)
        return IngredientsResponse(ingredients=ingredients)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"재료 추출 중 오류: {str(e)}")


@router.post("/summaries", response_model=RecipeSummaryResponse)
@inject
async def create_recipe_summary(
    req: RecipeSummaryRequest,
    recipe_service: RecipeService = Depends(Provide[Container.recipe_service]),
):
    """레시피 요약 API"""
    try:
        # 재료가 제공되지 않은 경우 자막에서 추출
        if req.ingredients:
            # 사용자 지정 재료가 있는 경우 (video_id가 필요하지만 여기서는 임시로 처리)
            # 실제로는 요청 모델을 수정해야 합니다
            pass
        
        # 요약 생성
        recipe = await recipe_service.create_summary(req.captions, req.description)
        if recipe is None:
            raise HTTPException(status_code=500, detail="요약 생성 실패")
        
        return RecipeSummaryResponse(recipe=recipe)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"요약 생성 중 오류: {str(e)}")


@router.post("/integrations", response_model=IntegrationResponse)
@inject
async def create_integration_summary(
    req: IntegrationRequest,
    recipe_service: RecipeService = Depends(Provide[Container.recipe_service]),
):
    """통합 API - 한 번의 요청으로 모든 과정 수행"""
    try:
        video_id = req.video_id
        video_type = req.video_type

        # 전체 레시피 생성 워크플로우 실행
        result = await recipe_service.create_full_recipe(video_id, video_type)
        if result is None:
            raise HTTPException(status_code=404, detail="레시피 생성 실패")

        # 응답 구성
        caption_response = CaptionResponse(
            video_id=video_id,
            lang_code=result["lang_code"],
            captions=result["captions"]
        )
        
        ingredients_response = IngredientsResponse(ingredients=result["recipe"].ingredients)
        
        summary_response = RecipeSummaryResponse(recipe=result["recipe"])
        
        return IntegrationResponse(
            video_id=video_id,
            captions=caption_response,
            ingredients=ingredients_response,
            summary=summary_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통합 처리 중 오류: {str(e)}")


@router.post("/recipes/custom", response_model=RecipeSummaryResponse)
@inject
async def create_recipe_with_custom_ingredients(
    req: dict,  # 임시로 dict 사용, 실제로는 새로운 모델 필요
    recipe_service: RecipeService = Depends(Provide[Container.recipe_service]),
):
    """사용자 지정 재료로 레시피 생성 API"""
    try:
        video_id = req.get("video_id")
        video_type = VideoType(req.get("video_type", "youtube"))
        custom_ingredients = req.get("ingredients", [])
        
        if not video_id:
            raise HTTPException(status_code=400, detail="video_id is required")
        
        # 사용자 지정 재료로 레시피 생성
        recipe = await recipe_service.create_recipe_with_custom_ingredients(
            video_id, video_type, custom_ingredients
        )
        
        if recipe is None:
            raise HTTPException(status_code=500, detail="레시피 생성 실패")
        
        return RecipeSummaryResponse(recipe=recipe)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"사용자 지정 레시피 생성 중 오류: {str(e)}")
