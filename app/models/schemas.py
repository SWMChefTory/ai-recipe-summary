from pydantic import BaseModel, HttpUrl
from typing import List, Dict

class SubtitleRequest(BaseModel):
    video_url: HttpUrl

class SubtitleResponse(BaseModel):
    video_id: str
    language: str
    subtitles: List[Dict]
