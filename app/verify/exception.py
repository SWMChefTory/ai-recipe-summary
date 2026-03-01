from enum import Enum
from typing import Optional, Any

from app.exception import RecipeSummaryException


class VerifyErrorCode(Enum):
    VERIFY_FAILED = ("VERIFY_001", "레시피 검증에 실패했습니다.")
    VERIFY_UPLOAD_ERROR = ("VERIFY_002", "비디오 업로드 중 오류가 발생했습니다.")
    VERIFY_NOT_RECIPE = ("VERIFY_003", "레시피 영상이 아닙니다.")
    VERIFY_NO_TOOL_CALL = ("VERIFY_004", "Gemini가 검증 결과를 반환하지 않았습니다.")

    def __init__(self, code: str, message: str):
        self._code = code
        self._message = message

    @property
    def code(self) -> str:
        return self._code

    @property
    def message(self) -> str:
        return self._message


class VerifyException(RecipeSummaryException):
    def __init__(self, code: Enum, detail: Optional[Any] = None):
        super().__init__(code, detail=detail)
        self.code = code
