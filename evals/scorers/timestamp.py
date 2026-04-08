"""
GT 기반 timestamp 정확도 scorer.

각 step.start가 영상에서 그 동작이 실제로 일어나는 시각과 얼마나 가까운지 측정.
GT(`fixtures/ground_truth/{video_id}.json`)의 cookingEvents와 매칭한다.

매칭은 LLM judge가 의미적으로 수행 (모델 step ↔ GT event).
허용 오차는 TOLERANCE_SECONDS = 2초.
"""

from typing import Optional, TypedDict, Callable
from .order import hms_to_seconds, seconds_to_hms


TOLERANCE_SECONDS = 2


class StepDetail(TypedDict, total=False):
    step: int
    model_start: str
    gt_start: str
    diff_sec: int
    matched_action: str
    ok: bool
    reason: str


class TimestampAccuracyResult(TypedDict):
    score: float
    correct: int
    total: int
    details: list[StepDetail]


# LLM matcher 시그니처: (step_text, candidate_events) -> matched_event or None
# 실제 구현은 google-genai로 따로 작성. 테스트 시에는 fake matcher 주입 가능.
LlmEventMatcher = Callable[[str, list[dict]], Optional[dict]]


def _step_to_text(step: dict) -> str:
    subtitle = step.get("subtitle", "")
    descs = step.get("descriptions", []) or []
    desc_text = " | ".join(d.get("text", "") for d in descs)
    return f"{subtitle} :: {desc_text}".strip(" :")


def score_step_timestamp_accuracy(
    steps: list[dict],
    gt_events: list[dict],
    matcher: LlmEventMatcher,
    tolerance_sec: int = TOLERANCE_SECONDS,
) -> TimestampAccuracyResult:
    """
    각 step.start vs 매칭된 GT event.start 의 차이가 tolerance 이내면 정답.

    Args:
        steps: 모델이 생성한 step 리스트 (start: hh:mm:ss).
        gt_events: GT cookingEvents [{action, start, end}], start/end는 초 단위.
        matcher: step 텍스트로 가장 가까운 GT event를 고르는 LLM 함수.
        tolerance_sec: 정답으로 간주할 시간 오차 (기본 2초).
    """
    if not steps:
        return {"score": 0.0, "correct": 0, "total": 0, "details": []}
    if not gt_events:
        return {
            "score": 0.0,
            "correct": 0,
            "total": len(steps),
            "details": [{"step": i, "reason": "no GT events"} for i in range(len(steps))],
        }

    correct = 0
    details: list[StepDetail] = []

    for si, step in enumerate(steps):
        model_start_sec = hms_to_seconds(step.get("start", ""))
        if model_start_sec is None:
            details.append({"step": si, "reason": "invalid model timecode"})
            continue

        matched = matcher(_step_to_text(step), gt_events)
        if matched is None:
            details.append({"step": si, "reason": "no GT match"})
            continue

        gt_start = matched.get("start")
        if gt_start is None:
            details.append({"step": si, "reason": "GT event missing start"})
            continue

        diff = abs(model_start_sec - int(gt_start))
        ok = diff <= tolerance_sec
        if ok:
            correct += 1
        details.append({
            "step": si,
            "model_start": step.get("start", ""),
            "gt_start": seconds_to_hms(int(gt_start)),
            "diff_sec": diff,
            "matched_action": matched.get("action", ""),
            "ok": ok,
        })

    return {
        "score": correct / len(steps),
        "correct": correct,
        "total": len(steps),
        "details": details,
    }
