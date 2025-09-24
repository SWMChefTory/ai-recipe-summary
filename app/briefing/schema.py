from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class BriefingRequest(BaseModel):
    video_id: str = Field(..., description="영상 ID")


class BriefingResponse(BaseModel):
    briefings: List[str] = Field(..., description="브리핑 내용")