from enum import Enum

from app.exception import RecipeSummaryException


class StepErrorCode(Enum):
    CHUNK_NOT_FOUND = ("SUMMARY_001", "캡션 청크를 찾을 수 없습니다.")
    STEP_GENERATE_FAILED = ("STEP_002", "단계 생성 중 오류가 발생했습니다.")
    
    def __init__(self, code: str, message: str):
        self._code = code
        self._message = message

    @property
    def code(self) -> str:
        return self._code

    @property
    def message(self) -> str:
        return self._message

class StepException(RecipeSummaryException):
    def __init__(self, code: Enum):
        super().__init__(code)
        self.code = code