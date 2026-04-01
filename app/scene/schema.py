from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class Scene(BaseModel):
    step: int = Field(..., description="해당 scene이 속하는 step 번호")
    label: str = Field(..., min_length=3, max_length=15, description="동작+대상 (3~15자)")
    start: str = Field(..., description="장면 시작 시간 (HH:MM:SS)")
    end: str = Field(..., description="장면 종료 시간 (HH:MM:SS)")
    important_score: int = Field(..., ge=1, le=10, alias="importantScore", description="초보자 기준 중요도 (1~10)")

    model_config = {"populate_by_name": True}


class SceneResponse(BaseModel):
    scenes: List[Scene] = Field(..., description="추출된 장면 목록")


class StepInput(BaseModel):
    subtitle: str = Field(..., description="조리단계 그룹 제목")
    start: float = Field(..., ge=0, description="조리단계 시작 시간 (초)")
    descriptions: List[StepDescriptionInput] = Field(..., description="조리단계별 설명 목록")


class StepDescriptionInput(BaseModel):
    text: str = Field(..., description="조리단계별 설명")
    start: float = Field(..., ge=0, description="조리단계별 설명 시작 시간 (초)")


class VideoSceneRequest(BaseModel):
    file_uri: str = Field(..., description="Gemini File URI")
    mime_type: str = Field(..., description="MIME Type")
    steps: List[StepInput] = Field(..., description="레시피 step 구조")
