from __future__ import annotations

from typing import List, Dict
from app.models.subtitle import Subtitle

_PRECISION = 2

def _seconds(val: float | str | None) -> float:
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


def normalize_subtitles(raw: List[Dict]) -> List[Subtitle]:
    """
    원본 자막 리스트를 정규화된 Subtitle 리스트로 변환

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
    out: List[Subtitle] = []

    for seg in raw:
        start_sec = _seconds(seg.get("start"))

        if "end" in seg:
            end_sec = _seconds(seg["end"])
        elif "duration" in seg:
            end_sec = start_sec + float(seg["duration"])
        else:
            raise ValueError("Subtitle segment requires 'end' or 'duration'.")

        start = round(start_sec, _PRECISION)
        end = round(end_sec, _PRECISION)

        out.append({"start": start, "end": end, "text": seg["text"]})

    out.sort(key=lambda x: x["start"])
    return out
