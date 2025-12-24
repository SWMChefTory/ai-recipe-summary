from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Header

from app.container import Container
from app.enum import LanguageType
from app.step.schema import StepRequest, StepResponse
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
    return StepResponse(steps=steps, language=language)