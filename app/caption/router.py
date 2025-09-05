from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.caption.schema import CaptionRequest, CaptionResponse
from app.caption.service import CaptionService
from app.container import Container

router = APIRouter()

@router.post("/v1/captions", response_model=CaptionResponse)
@inject
async def extract_captions(
    request: CaptionRequest,
    caption_service: CaptionService = Depends(Provide[Container.caption_service])
):
    captions, language = await caption_service.extract(request.video_id)
    return CaptionResponse(
        lang_code=language,
        captions=captions
    )