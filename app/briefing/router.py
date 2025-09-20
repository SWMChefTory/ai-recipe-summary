from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.briefing.schema import BriefingRequest, BriefingResponse
from app.briefing.service import BriefingService
from app.container import Container

router = APIRouter()

@router.post("/briefings", response_model=BriefingResponse)
@inject
async def get_briefing(
    request: BriefingRequest,
    briefing_service: BriefingService = Depends(Provide[Container.briefing_service])
):
    return BriefingResponse(briefings=await briefing_service.get(request.video_id))