from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .captions import CaptionResponse, VideoType
from .ingredients import Ingredient


class StepGroup(BaseModel):
    subtitle: str = Field(..., description="단계 제목")  # 예: "재료 준비하기", "조리 시작"
    start: float = Field(..., ge=0, description="단계 시작 시간")
    end: float = Field(..., ge=0, description="단계 끝 시간")
    descriptions: List[str] = Field(..., description="단계별 설명 목록")


class CookingProcessSummary(BaseModel):
    description: str = Field(..., description="해당 요리에 대한 간단한 설명 (1~2문장)")
    steps: List[StepGroup] = Field(..., description="단계 그룹 묶음")


class StepsSummaryRequest(BaseModel):
    video_id: str = Field(..., description="영상 ID")
    video_type: VideoType = Field(..., description="영상 플랫폼 타입")
    ingredients: List[Ingredient] = Field(description="재료 목록")
    captions_data: CaptionResponse = Field(..., description="자막")


class StepsSummaryResponse(BaseModel):
    summary: CookingProcessSummary
