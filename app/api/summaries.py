from fastapi import APIRouter, HTTPException
from app.models import *
from app.models.summary import VideoType
from app.services.youtube import get_subtitles_and_lang_code
from app.services.subtitles import normalize_subtitles

router = APIRouter()

@router.post("/summaries")
async def extract_subtitles(req: SummaryRequest):
    video_id = req.video_id
    video_type = req.video_type

    match video_type:
        case VideoType.youtube:
            subtitles, lang_code = get_subtitles_and_lang_code(video_id)

    if subtitles is None:
        raise HTTPException(status_code=404, detail="Subtitles not found")

    generated_subtitles: Subtitle = normalize_subtitles(subtitles)

    return generated_subtitles
