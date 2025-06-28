from __future__ import annotations

from typing import Dict
from pydantic import BaseModel, Field

from .subtitles import Subtitle
from .recipe import RecipeSummary

from enum import Enum

class VideoType(str, Enum):
    youtube = "youtube"
    instagram = "instagram"

class SummaryRequest(BaseModel):
    """POST /summary 요청 스키마"""
    video_id: str = Field(..., example="I3w8zAFa_G4")
    video_type: VideoType = Field(..., example="youtube")
    

class SummaryResponse(BaseModel):
    """POST /summary 응답 스키마"""
    video_id: str
    subtitles: Dict[str, Subtitle]
    recipe: RecipeSummary
