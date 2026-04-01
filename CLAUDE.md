# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube 요리 영상에서 구조화된 레시피를 추출하는 AI 시스템. 두 개의 독립적인 파트로 구성:

1. **Python API** (`app/`) — FastAPI 기반 프로덕션 서버. Gemini로 영상 분석, 메타데이터/스텝/브리핑/검증 처리
2. **Eval 파이프라인** (`src/mastra/`) — Mastra + Braintrust 기반 품질 평가 및 프롬프트 최적화

## Commands

### Python API (프로덕션)

```bash
# 로컬 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Docker 빌드 & 실행
docker build -f docker/Dockerfile -t cheftory-ai-recipe-summary-server:latest .
docker compose -f docker/docker-compose.prod.yml up

# 의존성 설치
pip install -r requirements.txt
```

### Eval 파이프라인 (Mastra)

```bash
# 개발 서버 (Mastra agent playground)
npm run dev

# 전체 레시피 평가 (10개 스코어러, Braintrust) — normal 태그만 실행
npm run eval

# Phase 1 시각 분석 단독 평가
npm run eval:phase1

# Ground Truth 수집 (Gemini Pro로 1초 단위 분석)
npm run eval:collect

# 자동 프롬프트 개선 루프
npm run eval:improve

# 캐시된 레시피 무시하고 재생성
FORCE_REGENERATE=1 npm run eval
```

## Architecture

### Python API (`app/`)

FastAPI 서버, dependency-injector DI 컨테이너, Gemini Function Calling 기반.

```
POST /meta/video    → 메타데이터 추출 (title, ingredients, tags, servings)
POST /steps/video   → 조리 스텝 생성 (subtitle, descriptions, timestamps)
POST /briefings     → 댓글 기반 인사이트 (tips, 대체재, 주의사항)
POST /verify        → 레시피 영상 여부 검증 (file upload → Gemini)
DELETE /cleanup     → Gemini File 삭제
```

4개 도메인 모두 동일 패턴: `router → service → generator/extractor + client`
- **Generator/Extractor**: Gemini API 호출 (`.md` 프롬프트 + `.json` 도구 스펙)
- **Client**: 외부 API (YouTube Data API, Cloud Run 업로드 서비스)

환경변수:
- `GOOGLE_API_KEY` — YouTube API
- `GOOGLE_AI_API_KEY` — Gemini API
- `GEMINI_MODEL_ID` — 주 모델 (meta, step)
- `GEMINI_MODEL_ID_LITE` — 경량 모델 (briefing, verify)
- `GEMINI_FALLBACK_MODEL_ID` — 폴백 (기본: gemini-3.0-flash)
- `CLOUD_RUN_CAPTION_URLS` — 영상 업로드 서비스 URL (콤마 구분)

### Eval: 5-Node 파이프라인 (v3)

`src/mastra/tools/analyze-video.ts`에서 YouTube URL → 레시피 JSON 추출을 5개 노드로 처리:

```
Node1 (Flash 3, thinking:high) → 영상 → flat description [{content, start, end}]
                    ↓
         ┌─────────┼──────────┐
         ↓         ↓          ↓
Node2 (Flash 2.5)  Node3→5    Node4 (Flash-Lite)
재료/도구 추출     (순차)      메타데이터 추출
                    │
            Node3 (Pro 2.5)
            step 분할
                    │
            Node5 (Pro 2.5)
            recommendScene만 반환
         └─────────┼──────────┘
                    ↓
         코드에서 Node3 + Node5 병합
                    ↓
         Python API 구조로 변환 → 최종 레시피 JSON
```

실행 흐름: Node1 → parallel(Node2, Node3→Node5, Node4) → merge → 구조 변환

### 출력 구조 (Python API 호환)

```json
{
  "title": "string",
  "description": "string",
  "ingredients": [{"name": "string", "amount": "number|null", "unit": "string|null"}],
  "tags": ["string"],
  "servings": "number",
  "cook_time": "number",
  "steps": [{
    "subtitle": "string",
    "start": "number (초)",
    "descriptions": [{"text": "string", "start": "number (초)"}],
    "scenes": [{"label": "string", "start": "number (초)", "end": "number (초)"}]
  }]
}
```

- Node5는 `recommend` 배열만 반환 → 코드에서 Node3의 steps와 order 기준으로 병합
- 시간은 HH:MM:SS → 초(number)로 변환

### 프롬프트 관리

- `app/*/prompt/` — Python API 프롬프트 (`.md` 유저 프롬프트 + `.json` 도구 스펙)
- `src/mastra/prompts/{v1,v2,v3}/` — Eval 버전별 프롬프트 (현재 v3)
- `src/mastra/prompts/index.ts` — `loadPrompt(phase, version)` / `savePrompt()`

### 평가 시스템

- `src/mastra/evals/dataset.ts` — 22개 테스트 케이스, tag 분류 (normal/multi/unusual)
  - normal 16개: 일반 레시피 (eval 대상)
  - multi 2개: 멀티 레시피 영상 (원팬 파스타, 멸치국수)
  - unusual 4개: GT 깨짐/특이 케이스 (호떡, 순두부찌개, 봄동비빔밥, 짬뽕)
- `src/mastra/evals/fixtures/` — Ground Truth JSON + 캐시된 레시피
- `src/mastra/evals/scorers/` — 4개 파일:
  - `helpers.ts` — ParsedRecipe 타입, geminiClassifier (Flash 3 thinking), withRetry, getAllScenes
  - `structure.ts` — Completeness, IngredientRecall, AmountAccuracy, StepQuality
  - `scene.ts` — SceneTimestampAccuracy, SceneCoverage, SceneLabelConciseness, SceneStepAlignment
  - `clarity.ts` — CookingActionCoverage
- 뷰포트 체크: Playwright 별도 프로세스

### 모델 할당

| 역할 | 모델 | 용도 |
|------|------|------|
| Node1 | gemini-3-flash-preview (thinking:high) | 영상 직접 분석 |
| Node2 | gemini-2.5-flash | 재료/도구 추출 |
| Node3 | gemini-2.5-pro | step 분할 |
| Node4 | gemini-3.1-flash-lite-preview | 메타데이터 추출 |
| Node5 | gemini-2.5-pro | recommendScene 생성 |
| Scorer | gemini-3-flash-preview (thinking:medium) | LLM-as-Judge |

## Key Dependencies

### Python
- **FastAPI** + **uvicorn** — API 서버
- **google-genai** — Gemini API (Function Calling)
- **dependency-injector** — DI 컨테이너
- **prometheus-fastapi-instrumentator** — 메트릭 (`/metrics`)

### Node.js
- **Mastra** (`@mastra/core`) — Agent 프레임워크
- **@ai-sdk/google** + **ai** (Vercel AI SDK) — Gemini 호출
- **Braintrust** — eval 실행/추적
- **Playwright** — 뷰포트 테스트

## Notes

- 모든 프롬프트와 출력은 한국어
- Python API는 `google-genai` SDK, Eval은 Vercel AI SDK (`@ai-sdk/google`) — 설정 방식이 다름
- Gemini Pro 2.5는 rate limit이 빡빡함 — Node3→Node5 순차 실행
- `FORCE_REGENERATE=1`로 eval 캐시 무시 가능
- Docker: `docker/Dockerfile` + `docker/docker-compose.prod.yml`, `cheftory_network` 외부 네트워크 사용
- eval은 `normalDataset()`만 실행 (multi/unusual 제외)
