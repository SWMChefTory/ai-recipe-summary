from fastapi import APIRouter, Depends, HTTPException, Query
from dependency_injector.wiring import Provide, inject

from app.verify.service import VerifyService
from app.verify.schema import VerificationRequest, VerificationResponse, CleanupResponse
from app.container import Container

router = APIRouter()

@router.post("/verify", response_model=VerificationResponse)
@inject
async def verify_endpoint(
    request: VerificationRequest,
    verify_service: VerifyService = Depends(Provide[Container.verify_service])
) -> VerificationResponse:
    """
    주어진 비디오 ID의 콘텐츠가 레시피와 관련이 있는지 검증합니다.
    (YouTube URL을 직접 Gemini에 전달하여 멀티모달 검증 수행)
    """
    if not request.video_id:
        raise HTTPException(status_code=400, detail="video_id required")

    result = await verify_service.verify_recipe(request.video_id)
    return VerificationResponse(**result)

@router.delete("/cleanup", response_model=CleanupResponse)
async def cleanup_endpoint(
    file_uri: str = Query(..., description="삭제할 Gemini File URI (하위호환용, no-op)"),
) -> CleanupResponse:
    """하위호환성을 위해 유지. 실제 동작 없이 성공을 반환합니다."""
    return CleanupResponse(message="success")
