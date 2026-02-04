from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Header

from app.container import Container
from app.enum import LanguageType
from app.step.schema import StepRequest, StepResponse, VideoStepRequest
from app.step.service import StepService

router = APIRouter()

@router.post("/steps", response_model=StepResponse)
@inject
async def generate_steps(
    request: StepRequest,
    x_country_code: Annotated[str | None, Header(alias="X-Country-Code")] = None,
    step_service: StepService = Depends(Provide[Container.step_service]),
):
    country = (x_country_code or "").strip().upper()
    language = LanguageType.KR if country == "KR" else LanguageType.EN

    steps = await step_service.generate(request.captions, language)
    return StepResponse(steps=steps)


@router.post("/steps/video", response_model=StepResponse)
@inject
async def generate_steps_by_video(
    request: VideoStepRequest,
    x_country_code: Annotated[str | None, Header(alias="X-Country-Code")] = None,
    step_service: StepService = Depends(Provide[Container.step_service]),
):
    country = (x_country_code or "").strip().upper()
    language = LanguageType.KR if country == "KR" else LanguageType.EN

    steps = await step_service.generate_by_video(request.file_uri, request.mime_type, language)
    return StepResponse(steps=steps)
