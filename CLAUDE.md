# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube 요리 영상에서 구조화된 레시피를 추출하는 AI 시스템.

**Python API** (`app/`) — FastAPI 기반 프로덕션 서버. Vertex AI (Gemini)로 영상 분석, 메타데이터/스텝/장면/브리핑/검증 처리

## Commands

```bash
# 로컬 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Docker 빌드 & 실행
docker build -f docker/Dockerfile -t cheftory-ai-recipe-summary-server:latest .
docker compose -f docker/docker-compose.prod.yml up

# 의존성 설치
pip install -r requirements.txt
```

## Architecture

### Python API (`app/`)

FastAPI 서버, dependency-injector DI 컨테이너, Gemini Function Calling 기반.

```
POST /meta/video    → 메타데이터 추출 (title, ingredients, tags, servings)
POST /steps/video   → 조리 스텝 생성 (subtitle, descriptions, timestamps)
POST /scenes/video  → 영상 장면 추출 (step별 조리 동작 scene, importantScore)
POST /briefings     → 댓글 기반 인사이트 (tips, 대체재, 주의사항)
POST /verify        → 레시피 영상 여부 검증 (YouTube URL → Gemini 직접 전달)
```

5개 도메인 모두 동일 패턴: `router → service → generator/extractor + client`
- **Generator/Extractor**: Vertex AI (Gemini) API 호출 (`.md` 프롬프트 + `.json` 도구 스펙)
- **Client**: 외부 API (YouTube Data API)

### 호출 흐름

```
1. POST /verify          → YouTube URL 반환 (file_uri 필드에 YouTube URL)
2. POST /meta/video      → 메타데이터 (verify 결과의 YouTube URL 사용)
3. POST /steps/video     → 조리 스텝 (verify 결과의 YouTube URL 사용)
4. POST /scenes/video    → 장면 추출 (YouTube URL + steps 결과 사용)
5. POST /briefings       → 브리핑 (별도 호출)
```

### 프롬프트 관리

모든 프롬프트는 `app/prompts/` 하위에서 **per-prompt versioning**으로 관리한다.

레이아웃:
```
app/prompts/
├── registry.py                       # ACTIVE_VERSIONS (도메인.이름 → vN)
├── CHANGELOG.md                      # 인덱스
├── {domain}/
│   ├── {name}.v1.md                  # 유저 프롬프트 (버전별)
│   ├── {name}.v1.changelog.md        # 변경 사유 sidecar
│   ├── {name}.v2.md
│   ├── {name}.v2.changelog.md
│   └── {tool_name}.tool.json         # 도구 스펙 (버전 없음)
```

API:
```python
from app.prompts import prompt_path, tool_path
prompt_path("step.video_summarize")          # registry 기본 버전
prompt_path("step.video_summarize", "v1")    # 명시 버전 (평가/실험용)
tool_path("step.video_step")                 # 도구 스펙
```

우선순위: 명시 인자 > `PROMPT_OVERRIDES` env > `ACTIVE_VERSIONS` registry.

env override:
```bash
PROMPT_OVERRIDES="step.video_summarize=v1,meta.extract_ingredient=v2"
```

**새 버전 추가 절차 (필수)**:
1. `{name}.v{N}.md` 작성 (이전 버전 복사 후 수정)
2. `{name}.v{N}.changelog.md` 작성 — Why / Changes / Expected impact / Risks 포함
3. `registry.py`의 `ACTIVE_VERSIONS`에서 해당 키를 v{N}으로 갱신 (또는 평가 후 갱신)
4. `app/prompts/CHANGELOG.md`에 한 줄 추가

환경변수:
- `GOOGLE_API_KEY` — YouTube Data API
- `VERTEX_AI_PROJECT_ID` — GCP 프로젝트 ID
- `GOOGLE_APPLICATION_CREDENTIALS` — 서비스 계정 JSON 경로

## Key Dependencies

- **FastAPI** + **uvicorn** — API 서버
- **google-genai** — Vertex AI (Gemini) API (Function Calling)
- **dependency-injector** — DI 컨테이너
- **prometheus-fastapi-instrumentator** — 메트릭 (`/metrics`)

## Notes

- 모든 프롬프트와 출력은 한국어 (X-Country-Code 헤더로 영어 지원)
- Docker: `docker/Dockerfile` + `docker/docker-compose.prod.yml`, `cheftory_network` 외부 네트워크 사용
- Vertex AI 인증: 서비스 계정 JSON + `GOOGLE_APPLICATION_CREDENTIALS` 환경변수
