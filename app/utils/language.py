"""
언어 처리 유틸리티 함수들
"""

import logging
from typing import Optional

from app.constants import LANGUAGE_MAPPING, AudioConfig

logger = logging.getLogger(__name__)


def normalize_language_code(language: Optional[str]) -> str:
    """
    언어 코드를 2글자 ISO-639-1 형식으로 정규화
    
    Args:
        language: 입력 언어 코드 (예: 'korean', 'en-US', 'ko-kr')
        
    Returns:
        2글자 ISO-639-1 형식의 언어 코드 (예: 'ko', 'en')
    """
    if not language:
        return AudioConfig.DEFAULT_LANGUAGE
        
    # 소문자로 변환하고 공백 제거
    language_clean = language.lower().strip().replace('_', '-')
    
    # 매핑에서 찾기
    normalized = LANGUAGE_MAPPING.get(language_clean, language_clean)
    
    # 이미 2글자면 그대로 반환
    if len(normalized) == 2 and normalized.isalpha():
        return normalized
        
    # 하이픈이 있는 경우 첫 부분만 사용 (예: en-US -> en)
    if '-' in normalized:
        first_part = normalized.split('-')[0]
        if len(first_part) == 2 and first_part.isalpha():
            return first_part
            
    # 매핑되지 않은 경우 경고 로그 출력하고 기본값 반환
    logger.warning(f"알 수 없는 언어 코드: {language}, 기본값 '{AudioConfig.DEFAULT_LANGUAGE}' 사용")
    return AudioConfig.DEFAULT_LANGUAGE


def is_valid_language_code(language_code: str) -> bool:
    """
    언어 코드가 유효한 2글자 ISO-639-1 형식인지 확인
    
    Args:
        language_code: 확인할 언어 코드
        
    Returns:
        유효한 경우 True, 아니면 False
    """
    return (
        isinstance(language_code, str) and 
        len(language_code) == 2 and 
        language_code.isalpha() and 
        language_code.islower()
    )


def get_supported_languages() -> list[str]:
    """
    지원되는 언어 코드 목록 반환
    
    Returns:
        지원되는 2글자 언어 코드들의 리스트
    """
    supported_languages = set(LANGUAGE_MAPPING.values())
    return sorted(list(supported_languages)) 