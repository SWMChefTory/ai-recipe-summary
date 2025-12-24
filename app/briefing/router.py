from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Header

from app.briefing.schema import BriefingRequest, BriefingResponse
from app.briefing.service import BriefingService
from app.container import Container
from app.enum import LanguageType

router = APIRouter()

@router.post("/briefings", response_model=BriefingResponse)
@inject
async def get_briefing(
    request: BriefingRequest,
    x_country_code: Annotated[str | None, Header(alias="X-Country-Code")] = None,
    briefing_service: BriefingService = Depends(Provide[Container.briefing_service])
):
    country = (x_country_code or "").strip().upper()
    language = LanguageType.KR if country == "KR" else LanguageType.EN

    return BriefingResponse(briefings=await briefing_service.get(request.video_id, language))