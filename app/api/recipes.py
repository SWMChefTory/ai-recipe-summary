from typing import List, Optional, Tuple

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException

from app.api.error_handlers import (
    handle_api_errors,
    validate_captions,
    validate_video_request,
)
from app.constants import ErrorMessages
from app.container import Container
from app.models import *
from app.models.captions import VideoType
from app.services.captions import CaptionService
from app.services.ingredients import IngredientsService
from app.services.summaries import SummariesService
from app.services.youtube import YouTubeService

router = APIRouter()


@router.post("/captions", response_model=CaptionResponse)
@inject
@handle_api_errors("자막 추출 중 오류")
async def extract_captions(
    request: CaptionRequest,
    youtube_service: YouTubeService = Depends(Provide[Container.youtube_service]),
    caption_service: CaptionService = Depends(Provide[Container.caption_service]),
):
    """동영상에서 자막을 추출하여 정규화된 형태로 반환합니다."""
    validate_video_request(request.video_id, request.video_type.value)

    raw_captions, language_code = _extract_raw_captions(request, youtube_service)
    normalized_captions = caption_service.normalize_captions(raw_captions)
    caption_segments = _convert_to_caption_segments(normalized_captions)
    
    return CaptionResponse(
        lang_code=language_code,
        captions=caption_segments
    )


@router.post("/ingredients", response_model=IngredientsResponse)
@inject
@handle_api_errors("재료 추출 중 오류")
async def extract_ingredients(
    request: IngredientsRequest,
    ingredients_service: IngredientsService = Depends(Provide[Container.ingredients_service]),
    youtube_service: YouTubeService = Depends(Provide[Container.youtube_service]),
):
    """동영상 자막과 설명에서 재료 목록을 추출합니다."""
    validate_video_request(request.video_id, request.video_type.value)
    validate_captions(request.captions_data)
    
    # 유튜브 설명란에서 재료 추출 시도
    description_ingredients = _extract_from_description(
        request, youtube_service, ingredients_service
    )
    if description_ingredients:
        return IngredientsResponse(ingredients=description_ingredients)

    # 자막에서 재료 추출
    caption_ingredients = ingredients_service.extract_ingredients(request.captions_data, "")
    return IngredientsResponse(ingredients=caption_ingredients)


@router.post("/summaries", response_model=StepsSummaryResponse)
@inject
@handle_api_errors("요약 생성 중 오류")
async def create_cooking_summary(
    request: StepsSummaryRequest,
    summaries_service: SummariesService = Depends(Provide[Container.summaries_service]),
):
    """자막과 재료 정보를 기반으로 단계별 조리 과정 요약을 생성합니다."""
    validate_video_request(request.video_id, request.video_type.value)
    validate_captions(request.captions_data)
    
    if not request.ingredients:
        raise HTTPException(status_code=400, detail="재료 목록이 필요합니다")
    
    cooking_summary = await summaries_service.create_summary(
        request.video_id, 
        request.video_type, 
        request.captions_data, 
        request.ingredients
    )
    
    if cooking_summary is None:
        raise HTTPException(status_code=500, detail="요약 생성에 실패했습니다")
        
    return StepsSummaryResponse(summary=cooking_summary)


# Helper functions for better separation of concerns
def _extract_raw_captions(
    request: CaptionRequest, 
    youtube_service: YouTubeService
) -> Tuple[List[dict], str]:
    """동영상에서 원본 자막과 언어 코드를 추출합니다."""
    if request.video_type != VideoType.youtube:
        raise HTTPException(status_code=400, detail="현재 YouTube만 지원됩니다")
    
    extraction_result = youtube_service.extract_captions_with_language(request.video_id)
    if extraction_result is None:
        raise HTTPException(status_code=404, detail="자막을 찾을 수 없습니다")
    
    return extraction_result


def _convert_to_caption_segments(normalized_captions: List[dict]) -> List[CaptionSegment]:
    """정규화된 자막 딕셔너리를 CaptionSegment 객체로 변환합니다."""
    caption_segments = []
    for caption in normalized_captions:
        segment = CaptionSegment(
            start=caption["start"],
            end=caption["end"], 
            text=caption["text"]
        )
        caption_segments.append(segment)
    
    return caption_segments


def _extract_from_description(
    request: IngredientsRequest,
    youtube_service: YouTubeService,
    ingredients_service: IngredientsService
) -> Optional[List[Ingredient]]:
    """유튜브 동영상 설명란에서 재료를 추출합니다."""
    if request.video_type != VideoType.youtube:
        return None
        
    video_description = youtube_service.get_video_description(request.video_id)
    
    # 설명란이 유효한지 확인
    if not _is_valid_description(video_description):
        return None
    
    # 설명란에서 재료 추출 시도
    description_ingredients = ingredients_service.extract_ingredients(
        request.captions_data, video_description
    )
    
    return description_ingredients if description_ingredients else None


def _is_valid_description(description: str) -> bool:
    """동영상 설명란이 재료 추출에 유효한지 확인합니다."""
    if not description:
        return False
        
    error_messages = [
        ErrorMessages.GOOGLE_API_KEY_MISSING,
        ErrorMessages.VIDEO_NOT_FOUND,
        ErrorMessages.RESPONSE_KEY_MISSING
    ]
    
    return not any(error_msg in description for error_msg in error_messages)
