from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .captions import CaptionResponse, VideoType


class Ingredient(BaseModel):
    name: str = Field(..., description="재료명")
    amount: Optional[float] = Field(None, ge=0)
    unit: Optional[str] = Field(None, max_length=10)


class IngredientsRequest(BaseModel):
    """재료 추출 요청"""
    video_id: str = Field(..., description="영상 ID")
    video_type: VideoType = Field(..., description="영상 플랫폼 타입")
    captions_data: CaptionResponse = Field(..., description="자막")


class IngredientsResponse(BaseModel):
    """재료 추출 응답"""
    ingredients: List[Ingredient]
