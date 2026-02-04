from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Header

from app.container import Container
from app.enum import LanguageType
from app.meta.schema import MetaRequest, MetaResponse, VideoMetaRequest
from app.meta.service import MetaService

router = APIRouter()

@router.post("/meta", response_model=MetaResponse)
@inject
async def extract_meta(
    request: MetaRequest,
    x_country_code: Annotated[str | None, Header(alias="X-Country-Code")] = None,
    meta_service: MetaService = Depends(Provide[Container.meta_service])
):
    country = (x_country_code or "").strip().upper()
    language = LanguageType.KR if country == "KR" else LanguageType.EN

    return await meta_service.extract(request.video_id, request.captions, language)


@router.post("/meta/video", response_model=MetaResponse)
@inject
async def extract_meta_by_video(
    request: VideoMetaRequest,
    x_country_code: Annotated[str | None, Header(alias="X-Country-Code")] = None,
    meta_service: MetaService = Depends(Provide[Container.meta_service])
):
    country = (x_country_code or "").strip().upper()
    language = LanguageType.KR if country == "KR" else LanguageType.EN

    return await meta_service.extract_by_video(request.video_id, request.file_uri, request.mime_type, language)
