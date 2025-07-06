from __future__ import annotations

from typing import Dict, List

from app.models.caption import Caption
from app.services.base import BaseService

_PRECISION = 2


class CaptionService(BaseService):
    """자막 처리 서비스"""

    def __init__(self, precision: int = _PRECISION):
        super().__init__()
        self.precision = precision

    def seconds(self, val: float | str | None) -> float:
        """
        입력값을 초 단위의 실수로 변환

        - float / int  : 이미 초 단위 숫자인 경우 ⇒ 그대로 반환
        - "HH:MM:SS"   : 시·분·초 문자열 ⇒ 초로 환산해 반환
        """
        if val is None:
            raise ValueError("time value missing")

        if isinstance(val, (int, float)):
            return float(val)

        h, m, s = val.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    def normalize_captions(self, raw_captions: List[Dict]) -> List[Dict]:
        """
        원본 자막 리스트를 정규화된 Caption 리스트로 변환

        변환 결과 스키마
        {
            "start": float,  # 영상 시작 기준 초(second) — 소수점 2자리까지
            "end":   float,  # 영상 시작 기준 초(second) — 소수점 2자리까지
            "text":  str     # 자막 텍스트(원문 그대로)
        }

        지원하는 입력 포맷
        - YouTube‑Transcript‑API
            {"text": str, "start": float, "duration": float}

        - Whisper / OpenAI STT
            {"text": str, "start": float, "end": float}
        """
        out: List[Dict] = []

        for seg in raw_captions:
            start_sec = self.seconds(seg.get("start"))

            if "end" in seg:
                end_sec = self.seconds(seg["end"])
            elif "duration" in seg:
                end_sec = start_sec + float(seg["duration"])
            else:
                raise ValueError("Caption segment requires 'end' or 'duration'.")

            start = round(start_sec, self.precision)
            end = round(end_sec, self.precision)

            out.append({"start": start, "end": end, "text": seg["text"]})

        out.sort(key=lambda x: x["start"])
        return out


# 하위 호환성을 위한 함수들 (추후 제거 예정)
def _seconds(val: float | str | None) -> float:
    """@deprecated: CaptionService.seconds() 사용 권장"""
    service = CaptionService()
    return service.seconds(val)


def normalize_captions(raw_captions: List[Dict]) -> List[Dict]:
    """@deprecated: CaptionService.normalize_captions() 사용 권장"""
    service = CaptionService()
    return service.normalize_captions(raw_captions)
