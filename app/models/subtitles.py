from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field


class SubtitleSegment(BaseModel):
    """자막 한 줄"""
    start: float = Field(..., ge=0)
    end:   float = Field(..., ge=0)
    text:  str


class Subtitle(BaseModel):
    """단일 언어 자막"""
    lang_code: str = Field(..., pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    segments:  List[SubtitleSegment]
