from enum import Enum

from app.exception import RecipeSummaryException


class BriefingErrorCode(Enum):
    BRIEFING_COMMENTS_EXTRACT_FAILED = ("BRIEFING_001", "댓글 추출 중 오류가 발생했습니다.")
    BRIEFING_COMMENTS_FILTER_FAILED = ("BRIEFING_002", "댓글 필터링 중 오류가 발생했습니다.")
    BRIEFING_GENERATE_FAILED = ("BRIEFING_003", "브리핑 생성 중 오류가 발생했습니다.")
    
    def __init__(self, code: str, message: str):
        self._code = code
        self._message = message

    @property
    def code(self) -> str:
        return self._code

    @property
    def message(self) -> str:
        return self._message

class BriefingException(RecipeSummaryException):
    def __init__(self, code: Enum):
        super().__init__(code)
        self.code = code