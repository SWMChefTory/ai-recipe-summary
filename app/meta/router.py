from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.container import Container
from app.meta.schema import MetaRequest, MetaResponse
from app.meta.service import MetaService

router = APIRouter()

@router.post("/meta", response_model=MetaResponse)
@inject
async def extract_meta(
    request: MetaRequest,
    meta_service: MetaService = Depends(Provide[Container.meta_service])
):
    return await meta_service.extract(request.video_id, request.captions)