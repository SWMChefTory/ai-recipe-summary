"""API 에러 처리 공통 함수들"""

import logging
from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def handle_api_errors(error_message_prefix: str = "API 오류"):
    """API 엔드포인트 에러 처리 데코레이터"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise  # HTTPException은 그대로 전파
            except Exception as e:
                logger.exception(f"{error_message_prefix}: {str(e)}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"{error_message_prefix}: {str(e)}"
                )
        return wrapper
    return decorator


def validate_video_request(video_id: str, video_type: str) -> None:
    """비디오 요청 유효성 검사"""
    if not video_id or not video_id.strip():
        raise HTTPException(status_code=400, detail="video_id는 필수입니다")
    
    if not video_type or not video_type.strip():
        raise HTTPException(status_code=400, detail="video_type은 필수입니다")


def validate_captions(caption_response) -> None:
    """자막 데이터 유효성 검사"""
    if not caption_response:
        raise HTTPException(status_code=400, detail="captions는 필수입니다")
    
    if not hasattr(caption_response, 'captions') or not caption_response.captions:
        raise HTTPException(status_code=400, detail="자막 데이터가 비어있습니다")
    
    if not hasattr(caption_response, 'lang_code') or not caption_response.lang_code:
        raise HTTPException(status_code=400, detail="언어 코드가 필요합니다") 