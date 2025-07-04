from fastapi import APIRouter, HTTPException

from app.models import *
from app.models.summary import VideoType
from app.services.captions import normalize_captions
from app.services.ingredients import extract_ingredients
from app.services.summaries import summarize
from app.services.youtube import get_subtitles_and_lang_code, get_youtube_description

router = APIRouter()

@router.post("/captions", response_model=CaptionResponse)
async def extract_captions(req: CaptionRequest):
    """자막 추출 API"""
    video_id = req.video_id
    video_type = req.video_type

    captions = None
    lang_code = None
    
    match video_type:
        case VideoType.youtube:
            result = get_subtitles_and_lang_code(video_id)
            if result is not None:
                captions, lang_code = result

    if captions is None or lang_code is None:
        raise HTTPException(status_code=404, detail="Captions not found")

    normalized_captions = normalize_captions(captions)
    
    return CaptionResponse(
        video_id=video_id,
        lang_code=lang_code,
        captions=normalized_captions
    )


@router.post("/ingredients", response_model=IngredientsResponse)
async def extract_ingredients_api(req: IngredientsRequest):
    """재료 추출 API"""
    try:
        ingredients = extract_ingredients(req.captions, req.description)
        return IngredientsResponse(ingredients=ingredients)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"재료 추출 중 오류: {str(e)}")


@router.post("/summaries", response_model=RecipeSummaryResponse)
async def create_recipe_summary(req: RecipeSummaryRequest):
    """레시피 요약 API"""
    try:
        # 재료가 제공되지 않은 경우 자막에서 추출
        ingredients = req.ingredients
        if not ingredients:
            ingredients = extract_ingredients(req.captions, req.description)
        
        # 요약 생성 (기존 summarize 함수 활용)
        summary_result = summarize(req.captions, req.description)
        
        # JSON 파싱해서 RecipeSummary 객체 생성
        import json
        summary_data = json.loads(summary_result)
        
        # RecipeSummary 객체 생성 (필요한 필드만 추출)
        recipe = RecipeSummary(
            title=summary_data.get("title", ""),
            summary=summary_data.get("summary", ""),
            total_time_sec=summary_data.get("total_time_sec"),
            ingredients=ingredients,
            steps=summary_data.get("steps", [])
        )
        
        return RecipeSummaryResponse(recipe=recipe)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"요약 생성 중 오류: {str(e)}")


@router.post("/integrations", response_model=IntegrationResponse)
async def create_integration_summary(req: IntegrationRequest):
    """통합 API - 한 번의 요청으로 모든 과정 수행"""
    video_id = req.video_id
    video_type = req.video_type

    try:
        # 1. 자막 추출
        captions = None
        lang_code = None
        description = ""
        
        match video_type:
            case VideoType.youtube:
                result = get_subtitles_and_lang_code(video_id)
                if result is not None:
                    captions, lang_code = result
                description = get_youtube_description(video_id)

        if captions is None or lang_code is None:
            raise HTTPException(status_code=404, detail="Captions not found")

        normalized_captions = normalize_captions(captions)
        
        # 2. 재료 추출
        ingredients = extract_ingredients(normalized_captions, description)
        
        # 3. 요약 생성
        summary_result = summarize(normalized_captions, description)
        
        # JSON 파싱해서 RecipeSummary 객체 생성
        import json
        summary_data = json.loads(summary_result)
        
        recipe = RecipeSummary(
            title=summary_data.get("title", ""),
            summary=summary_data.get("summary", ""),
            total_time_sec=summary_data.get("total_time_sec"),
            ingredients=ingredients,
            steps=summary_data.get("steps", [])
        )
        
        # 응답 구성
        caption_response = CaptionResponse(
            video_id=video_id,
            lang_code=lang_code,
            captions=normalized_captions
        )
        
        ingredients_response = IngredientsResponse(ingredients=ingredients)
        
        summary_response = RecipeSummaryResponse(recipe=recipe)
        
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
