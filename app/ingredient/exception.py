from enum import Enum

from app.exception import RecipeSummaryException


class IngredientErrorCode(Enum):
    INGREDIENT_EXTRACT_FAILED = ("INGREDIENT_001", "재료 추출 중 오류가 발생했습니다.")
    INGREDIENT_NOT_FOUND = ("INGREDIENT_002", "재료를 찾을 수 없습니다.")
    
    def __init__(self, code: str, message: str):
        self._code = code
        self._message = message

    @property
    def code(self) -> str:
        return self._code

    @property
    def message(self) -> str:
        return self._message

class IngredientException(RecipeSummaryException):
    def __init__(self, code: Enum):
        super().__init__(code)
        self.code = code