from enum import Enum

from app.exception import RecipeSummaryException


class MetaErrorCode(Enum):
    META_EXTRACT_FAILED = ("META_001", "메타데이터 추출 중 오류가 발생했습니다.")
    META_API_INVOKE_FAILED = ("META_002", "API 호출 중 오류가 발생했습니다.")
    META_NOT_FOUND = ("META_003", "메타데이터를 찾을 수 없습니다.")
    META_INGREDIENTS_EXTRACT_FAILED = ("META_004", "재료 추출 중 오류가 발생했습니다.")

    
    def __init__(self, code: str, message: str):
        self._code = code
        self._message = message

    @property
    def code(self) -> str:
        return self._code

    @property
    def message(self) -> str:
        return self._message

class MetaException(RecipeSummaryException):
    def __init__(self, code: Enum):
        super().__init__(code)
        self.code = code