from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict
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
    (비디오를 업로드하여 Gemini 멀티모달 검증 수행)
    """
    if not request.video_id:
        raise HTTPException(status_code=400, detail="video_id required")

    # VerifyService를 사용하여 비디오 ID로 레시피 검증
    # 예외 발생 시 전역 핸들러가 처리함
    result = await verify_service.verify_recipe(request.video_id)
    return VerificationResponse(**result)

@router.delete("/cleanup", response_model=CleanupResponse)
@inject
async def cleanup_endpoint(
    file_uri: str = Query(..., description="삭제할 Gemini File URI"),
    verify_service: VerifyService = Depends(Provide[Container.verify_service])
) -> CleanupResponse:
    """
    분석이 완료된 Gemini 파일을 삭제하여 리소스를 정리합니다.
    """
    await verify_service.delete_file_by_url(file_uri)
    return CleanupResponse(message="success")
