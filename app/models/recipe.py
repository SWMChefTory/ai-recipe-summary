from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class Ingredient(BaseModel):
    name: str = Field(..., description="소문자 재료명")
    amount: Optional[float] = Field(None, ge=0)
    unit: Optional[str] = Field(None, max_length=10)


class Step(BaseModel):
    start: float = Field(..., ge=0)
    end: float = Field(..., ge=0)
    description: str = Field(..., max_length=50, description="50자 이내, '~하기'")


class RecipeSummary(BaseModel):
    title: str
    summary: str
    total_time_sec: Optional[int] = Field(None, ge=0)
    ingredients: List[Ingredient]
    steps: Optional[List[Step]] = None
