from typing import List

from pydantic import BaseModel, Field

from app.enums import VideoType


class CaptionSegment(BaseModel):
    """개별 자막 세그먼트"""
    start: float = Field(..., description="시작 시간 (초)")
    end: float = Field(..., description="종료 시간 (초)")
    text: str = Field(..., description="자막 텍스트")


class CaptionRequest(BaseModel):
    """자막 추출 요청"""
    video_id: str = Field(..., description="YouTube 영상 ID")
    video_type: VideoType = Field(..., description="영상 플랫폼 타입")


class CaptionResponse(BaseModel):
    """자막 추출 응답"""
    lang_code: str = Field(..., description="언어 코드")
    captions: List[CaptionSegment] = Field(..., description="정규화된 자막 세그먼트 리스트")