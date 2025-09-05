from enum import Enum
from typing import Any, Optional


class BusinessException(Exception):
    def __init__(self, code: Enum, *, status_code: int = 400, detail: Optional[Any] = None):
        super().__init__(getattr(code, "message", str(code)))
        self.code = code   
        self.status_code = status_code
        self.detail = detail

    @property
    def error_code(self) -> str:
        return getattr(self.code, "code", getattr(self.code, "name", "UNKNOWN"))

    @property
    def error_message(self) -> str:
        return getattr(self.code, "message", str(self.code))

    def to_dict(self) -> dict:
        body = {
            "error_code": self.error_code,
            "error_message": self.error_message,
        }
        return body


class RecipeSummaryException(BusinessException):
    def __init__(self, code: Enum, *, status_code: int = 400, detail: Optional[Any] = None):
        super().__init__(code, status_code=status_code, detail=detail)