from __future__ import annotations

from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field

from .caption import Caption
from .recipe import Ingredient, RecipeSummary


class VideoType(str, Enum):
    youtube = "youtube"
    instagram = "instagram"

class SummaryRequest(BaseModel):
    """POST /summary 요청 스키마"""
    video_id: str = Field(..., description="YouTube 영상 ID")
    video_type: VideoType = Field(..., description="영상 플랫폼 타입")
    

class SummaryResponse(BaseModel):
    """POST /summary 응답 스키마"""
    video_id: str
    captions: Dict[str, Caption]
    recipe: RecipeSummary


# 새로운 분리된 API들을 위한 모델들
class CaptionRequest(BaseModel):
    """자막 추출 요청"""
    video_id: str = Field(..., description="YouTube 영상 ID")
    video_type: VideoType = Field(..., description="영상 플랫폼 타입")


class CaptionResponse(BaseModel):
    """자막 추출 응답"""
    video_id: str
    lang_code: str
    captions: List[Dict] = Field(description="정규화된 자막 세그먼트 리스트")


class IngredientsRequest(BaseModel):
    """재료 추출 요청"""
    captions: List[Dict] = Field(description="자막 세그먼트 리스트")
    description: str = Field(default="", description="영상 설명 (선택사항)")


class IngredientsResponse(BaseModel):
    """재료 추출 응답"""
    ingredients: List[Ingredient]


class RecipeSummaryRequest(BaseModel):
    """레시피 요약 요청"""
    captions: List[Dict] = Field(description="자막 세그먼트 리스트")
    description: str = Field(default="", description="영상 설명")
    ingredients: List[Ingredient] = Field(default=[], description="재료 리스트 (선택사항)")


class RecipeSummaryResponse(BaseModel):
    """레시피 요약 응답"""
    recipe: RecipeSummary


class IntegrationRequest(BaseModel):
    """통합 API 요청 (기존 summaries 대체)"""
    video_id: str = Field(..., description="YouTube 영상 ID")
    video_type: VideoType = Field(..., description="영상 플랫폼 타입")


class IntegrationResponse(BaseModel):
    """통합 API 응답"""
    video_id: str
    captions: CaptionResponse
    ingredients: IngredientsResponse  
    summary: RecipeSummaryResponse
