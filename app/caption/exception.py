from enum import Enum

from app.exception import RecipeSummaryException


class CaptionErrorCode(Enum):
    CAPTION_NOT_FOUND = ("CAPTION_001", "자막이 존재하지 않습니다.")
    CAPTION_DOWNLOAD_FAILED = ("CAPTION_002", "자막 다운로드 중 오류가 발생했습니다.")
    CAPTION_EXTRACT_FAILED = ("CAPTION_003", "자막 추출 중 오류가 발생했습니다.")
    CAPTION_NOT_RECIPE = ("CAPTION_004", "자막에서 레시피를 찾을 수 없습니다.")
    CAPTION_VALIDATE_FAILED = ("CAPTION_005", "자막 검증 중 오류가 발생했습니다.")
    CAPTION_MANUAL_LANG_FAILED = ("CAPTION_006", "수동 자막 언어 추출 중 오류가 발생했습니다.")
    CAPTION_AUTO_LANG_FAILED = ("CAPTION_007", "자동 자막 언어 추출 중 오류가 발생했습니다.")
    
    def __init__(self, code: str, message: str):
        self._code = code
        self._message = message

    @property
    def code(self) -> str:
        return self._code

    @property
    def message(self) -> str:
        return self._message

class CaptionException(RecipeSummaryException):
    def __init__(self, code: Enum):
        super().__init__(code)
        self.code = code