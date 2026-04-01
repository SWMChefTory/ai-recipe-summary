from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# --- Request ---

class StepDescriptionInput(BaseModel):
    text: str = Field(..., description="조리단계별 설명")
    start: float = Field(..., ge=0, description="조리단계별 설명 시작 시간 (초)")


class StepInput(BaseModel):
    step_id: UUID = Field(..., description="step UUID")
    subtitle: str = Field(..., description="조리단계 그룹 제목")
    start: float = Field(..., ge=0, description="조리단계 시작 시간 (초)")
    descriptions: List[StepDescriptionInput] = Field(..., description="조리단계별 설명 목록")


class VideoSceneRequest(BaseModel):
    file_uri: str = Field(..., description="Gemini File URI")
    mime_type: str = Field(..., description="MIME Type")
    steps: List[StepInput] = Field(..., description="레시피 step 구조")


# --- Response ---

class SceneOut(BaseModel):
    step_id: UUID = Field(..., description="해당 scene이 속하는 step UUID")
    label: str = Field(..., description="동작+대상")
    start: float = Field(..., description="장면 시작 시간 (초)")
    end: float = Field(..., description="장면 종료 시간 (초)")
    important_score: int = Field(..., ge=1, le=10, description="초보자 기준 중요도 (1~10)")


class SceneResponse(BaseModel):
    scenes: List[SceneOut] = Field(..., description="추출된 장면 목록")
