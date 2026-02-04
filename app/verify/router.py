from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from dependency_injector.wiring import Provide, inject

from app.verify.service import VerifyService
from app.container import Container

router = APIRouter()

class VerificationRequest(BaseModel):
    video_id: str

@router.post("/verify")
@inject
async def verify_endpoint(
    request: VerificationRequest,
    verify_service: VerifyService = Depends(Provide[Container.verify_service])
) -> Dict[str, Any]:
    """
    주어진 비디오 ID의 콘텐츠가 레시피와 관련이 있는지 검증합니다.
    (비디오를 업로드하여 Gemini 멀티모달 검증 수행)
    """
    if not request.video_id:
        raise HTTPException(status_code=400, detail="video_id required")

    # VerifyService를 사용하여 비디오 ID로 레시피 검증
    # 예외 발생 시 전역 핸들러가 처리함
    result = await verify_service.verify_recipe(request.video_id)
    return result
