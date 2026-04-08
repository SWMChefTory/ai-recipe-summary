"""
Per-prompt versioned prompt loader.

디렉토리 레이아웃:
    app/prompts/
        registry.py                     # 활성 버전 매핑 (도메인.이름 → vN)
        {domain}/
            {name}.v1.md                # 버전별 유저 프롬프트
            {name}.v2.md
            {name}.tool.json            # 도구 스펙(버전 없음)

API:
    prompt_path("step.video_summarize")            # registry 기본 버전
    prompt_path("step.video_summarize", "v1")      # 명시적 버전 (평가/실험용)
    tool_path("step.video_step")                   # 도구 스펙 (버전 없음)

환경변수 override:
    PROMPT_OVERRIDES="step.video_summarize=v1,meta.extract_ingredient=v2"
    → 등록된 키만 override. 명시 버전 인자가 들어오면 env도 무시한다.
"""

import os
from functools import lru_cache
from pathlib import Path

from app.prompts.registry import ACTIVE_VERSIONS

_PROMPTS_ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def _env_overrides() -> dict[str, str]:
    raw = os.environ.get("PROMPT_OVERRIDES", "").strip()
    if not raw:
        return {}
    out: dict[str, str] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def reset_env_overrides_cache() -> None:
    """테스트에서 env 변경 후 호출."""
    _env_overrides.cache_clear()


def resolve_version(name: str, explicit: str | None = None) -> str:
    """우선순위: 명시 인자 > PROMPT_OVERRIDES env > registry 기본."""
    if explicit:
        return explicit
    overrides = _env_overrides()
    if name in overrides:
        return overrides[name]
    if name in ACTIVE_VERSIONS:
        return ACTIVE_VERSIONS[name]
    raise KeyError(f"Unknown prompt name: '{name}'. Add it to ACTIVE_VERSIONS in registry.py.")


def _split_name(name: str) -> tuple[str, str]:
    if "." not in name:
        raise ValueError(
            f"Prompt name must be in '{{domain}}.{{name}}' form, got '{name}'."
        )
    domain, prompt_name = name.split(".", 1)
    return domain, prompt_name


def prompt_path(name: str, version: str | None = None) -> Path:
    """
    버전 적용된 유저 프롬프트(.md) 파일 경로.

    Args:
        name: "{domain}.{prompt_name}" (예: "step.video_summarize").
        version: 명시 버전. None이면 env override → registry 기본 순으로 결정.
    """
    domain, prompt_name = _split_name(name)
    resolved = resolve_version(name, version)
    candidate = _PROMPTS_ROOT / domain / f"{prompt_name}.{resolved}.md"
    if not candidate.is_file():
        raise FileNotFoundError(
            f"Prompt file not found: '{candidate}' "
            f"(name='{name}', version='{resolved}')"
        )
    return candidate


def tool_path(name: str) -> Path:
    """
    도구 스펙(.tool.json) 파일 경로. 도구 스펙은 버전 없이 단일 파일로 관리한다.

    Args:
        name: "{domain}.{tool_name}" (예: "step.video_step").
    """
    domain, tool_name = _split_name(name)
    candidate = _PROMPTS_ROOT / domain / f"{tool_name}.tool.json"
    if not candidate.is_file():
        raise FileNotFoundError(f"Tool spec file not found: '{candidate}' (name='{name}')")
    return candidate
