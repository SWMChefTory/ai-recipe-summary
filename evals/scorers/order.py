"""
결정적 scorer 모듈 — LLM 호출 없음, GT 불필요.

제공 메트릭:
- score_step_chronological_order: step / description start가 영상 시간순(monotonic non-decreasing)인가
- score_timestamp_sanity: 형식·범위·step↔desc 정합성 등 명백한 시간 오류 검출
"""

from typing import Optional, TypedDict


class OrderResult(TypedDict):
    score: float
    violations: list[str]
    total_pairs: int


class SanityResult(TypedDict):
    score: float
    issues: list[str]


def hms_to_seconds(t: str) -> Optional[int]:
    """'00:09:43' → 583. 형식 위반 시 None."""
    if not isinstance(t, str):
        return None
    parts = t.split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, s = (int(p) for p in parts)
    except ValueError:
        return None
    if m >= 60 or s >= 60 or h < 0 or m < 0 or s < 0:
        return None
    return h * 3600 + m * 60 + s


def seconds_to_hms(sec: int) -> str:
    sec = max(0, int(sec))
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


def score_step_chronological_order(steps: list[dict]) -> OrderResult:
    """
    step 간, 그리고 같은 step 내 descriptions 간 start가
    monotonic non-decreasing(영상 시간순)인지 검사.

    점수 = (지킨 인접 쌍 수) / (전체 인접 쌍 수)
    인접 쌍이 0개면 1.0 반환.
    """
    violations: list[str] = []
    total_pairs = 0
    ok_pairs = 0

    # 1) step 간 순서
    step_starts = [hms_to_seconds(s.get("start", "")) for s in steps]
    for i in range(len(step_starts) - 1):
        total_pairs += 1
        a, b = step_starts[i], step_starts[i + 1]
        if a is None or b is None:
            violations.append(f"step{i}/step{i+1}: invalid timecode")
            continue
        if a <= b:
            ok_pairs += 1
        else:
            violations.append(
                f"step{i}({steps[i].get('start')}) > step{i+1}({steps[i+1].get('start')})"
            )

    # 2) 같은 step 내 description 간 순서
    for si, step in enumerate(steps):
        descs = step.get("descriptions", []) or []
        d_starts = [hms_to_seconds(d.get("start", "")) for d in descs]
        for i in range(len(d_starts) - 1):
            total_pairs += 1
            a, b = d_starts[i], d_starts[i + 1]
            if a is None or b is None:
                violations.append(f"step{si}.desc{i}/desc{i+1}: invalid timecode")
                continue
            if a <= b:
                ok_pairs += 1
            else:
                violations.append(
                    f"step{si}.desc{i}({descs[i].get('start')}) > "
                    f"step{si}.desc{i+1}({descs[i+1].get('start')})"
                )

    score = ok_pairs / total_pairs if total_pairs else 1.0
    return {"score": score, "violations": violations, "total_pairs": total_pairs}


def score_timestamp_sanity(
    steps: list[dict],
    video_duration_sec: Optional[int] = None,
) -> SanityResult:
    """
    GT 없이 잡을 수 있는 명백한 시간 오류:
      - hh:mm:ss 형식 위반
      - 음수 / 영상 길이 초과 (video_duration_sec 주어진 경우)
      - 같은 step 내 description.start가 step.start보다 앞섬

    점수 = max(0, 1 - issues / max(steps, 1))
    """
    issues: list[str] = []
    for si, step in enumerate(steps):
        s_raw = step.get("start", "")
        s = hms_to_seconds(s_raw)
        if s is None:
            issues.append(f"step{si}: invalid format '{s_raw}'")
            continue
        if video_duration_sec is not None and s > video_duration_sec:
            issues.append(f"step{si}: {s}s > video {video_duration_sec}s")

        for di, d in enumerate(step.get("descriptions", []) or []):
            d_raw = d.get("start", "")
            ds = hms_to_seconds(d_raw)
            if ds is None:
                issues.append(f"step{si}.desc{di}: invalid format '{d_raw}'")
                continue
            if ds < s:
                issues.append(
                    f"step{si}.desc{di}({d_raw}) < step.start({s_raw})"
                )
            if video_duration_sec is not None and ds > video_duration_sec:
                issues.append(
                    f"step{si}.desc{di}: {ds}s > video {video_duration_sec}s"
                )

    total_steps = max(len(steps), 1)
    score = max(0.0, 1 - len(issues) / total_steps)
    return {"score": score, "issues": issues}
