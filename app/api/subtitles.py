from fastapi import APIRouter, HTTPException
from app.models.schemas import SubtitleRequest, SubtitleResponse
from app.services.youtube import get_video_id_from_youtube, get_subtitles

router = APIRouter()

@router.post("/subtitles", response_model=SubtitleResponse)
async def extract_subtitles(req: SubtitleRequest):
    video_id = get_video_id_from_youtube(req.video_url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    resp = get_subtitles(video_id)
    if not resp:
        raise HTTPException(status_code=404, detail="No subtitles found")
    
    return resp
