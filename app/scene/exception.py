from enum import Enum

from app.exception import RecipeSummaryException


class SceneErrorCode(Enum):
    SCENE_GENERATE_FAILED = ("SCENE_001", "장면 생성 중 오류가 발생했습니다.")

    def __init__(self, code: str, message: str):
        self._code = code
        self._message = message

    @property
    def code(self) -> str:
        return self._code

    @property
    def message(self) -> str:
        return self._message


class SceneException(RecipeSummaryException):
    def __init__(self, code: Enum):
        super().__init__(code)
        self.code = code
