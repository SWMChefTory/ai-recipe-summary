from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.caption.schema import CaptionRequest, CaptionResponse
from app.caption.service import CaptionService
from app.container import Container

router = APIRouter()

@router.post("/captions", response_model=CaptionResponse)
@inject
async def extract_captions(
    request: CaptionRequest,
    caption_service: CaptionService = Depends(Provide[Container.caption_service])
):
    captions, lang_code = await caption_service.get_captions_with_lang_code(request.video_id)
    return CaptionResponse(
        lang_code=lang_code,
        captions=captions
    )