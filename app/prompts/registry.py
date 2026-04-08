"""
Per-prompt active version registry.

각 프롬프트마다 독립적으로 활성 버전을 지정한다.
글로벌 PROMPT_VERSION이 없으므로 서로 다른 프롬프트가 서로 다른 버전에 머무를 수 있다.

키 형식: "{domain}.{prompt_name}" (예: "step.video_summarize")

새 버전 추가 절차:
    1. app/prompts/{domain}/{name}.v{N}.md 파일 작성
    2. ACTIVE_VERSIONS의 해당 키를 v{N}으로 갱신
    3. (선택) 환경변수 PROMPT_OVERRIDES 로 임시 override 가능

A/B / 평가 시:
    - 평가 러너에서 prompt_path(name, version="v1") 처럼 명시적 버전을 넘기면
      registry/env를 우회해서 특정 버전만 로드 가능.
"""

ACTIVE_VERSIONS: dict[str, str] = {
    "meta.extract_ingredient": "v1",
    "meta.video_extract": "v1",
    "step.video_summarize": "v2",
    "scene.video_scene": "v1",
    "verify.verify": "v1",
    "briefing.user_prompt": "v1",
}
