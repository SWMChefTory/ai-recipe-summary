from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.container import Container
from app.step.schema import StepRequest, StepResponse
from app.step.service import StepService

router = APIRouter()

@router.post("/steps", response_model=StepResponse)
@inject
async def generate_steps(
    request: StepRequest,
    step_service: StepService = Depends(Provide[Container.step_service])
):
    return StepResponse(steps=await step_service.generate(request.captions))