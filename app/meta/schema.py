from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.caption.schema import Caption


class Ingredient(BaseModel):
    name: str = Field(..., description="재료명")
    amount: Optional[float] = Field(None, ge=0)
    unit: Optional[str] = Field(None, max_length=10)


class MetaRequest(BaseModel):
    """메타데이터 추출 요청"""
    video_id: str = Field(..., description="영상 ID")
    captions: List[Caption] = Field(..., description="자막")


class MetaResponse(BaseModel):
    """메타데이터 추출 응답"""
    description: str = Field(..., description="요리에 대한 간단한 설명(최대 60자)")
    ingredients: List[Ingredient]
    tags: List[str] = Field(description="태그(2~4개)")
    servings: int = Field(ge=1, description="몇 인분")
    cook_time: int = Field(..., description="요리 시간(분)")