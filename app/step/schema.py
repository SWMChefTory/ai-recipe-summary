from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class StepGroup(BaseModel):
    subtitle: str = Field(..., description="조리단계 그룹 제목")
    start: float = Field(..., ge=0, description="조리단계 그룹 시작 시간")
    descriptions: List[StepDescription] = Field(..., description="조리단계 그룹별 설명 목록")


class StepDescription(BaseModel):
    text: str = Field(..., description="조리단계별 설명")
    start: float = Field(..., ge=0, description="조리단계별 설명 시작 시간")


class StepResponse(BaseModel):
    steps: List[StepGroup] = Field(..., description="조리단계 그룹 목록")


class VideoStepRequest(BaseModel):
    file_uri: str = Field(..., description="Gemini File URI")
    mime_type: str = Field(..., description="MIME Type")
