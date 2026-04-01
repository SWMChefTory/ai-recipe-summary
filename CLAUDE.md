# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube 요리 영상에서 구조화된 레시피를 추출하는 AI 시스템.

**Python API** (`app/`) — FastAPI 기반 프로덕션 서버. Gemini로 영상 분석, 메타데이터/스텝/장면/브리핑/검증 처리

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
POST /verify        → 레시피 영상 여부 검증 (file upload → Gemini)
DELETE /cleanup     → Gemini File 삭제
```

5개 도메인 모두 동일 패턴: `router → service → generator/extractor + client`
- **Generator/Extractor**: Gemini API 호출 (`.md` 프롬프트 + `.json` 도구 스펙)
- **Client**: 외부 API (YouTube Data API, Cloud Run 업로드 서비스)

### 호출 흐름

```
1. POST /verify          → file_uri, mime_type 반환
2. POST /meta/video      → 메타데이터 (verify 결과의 file_uri 사용)
3. POST /steps/video     → 조리 스텝 (verify 결과의 file_uri 사용)
4. POST /scenes/video    → 장면 추출 (file_uri + steps 결과 사용)
5. POST /briefings       → 브리핑 (별도 호출)
6. DELETE /cleanup       → Gemini 파일 정리
```

### 프롬프트 관리

`app/*/prompt/` — 각 도메인별 프롬프트 (`.md` 유저 프롬프트 + `.json` 도구 스펙)

환경변수:
- `GOOGLE_API_KEY` — YouTube API
- `GOOGLE_AI_API_KEY` — Gemini API
- `GEMINI_MODEL_ID` — 주 모델 (meta, step, scene)
- `GEMINI_MODEL_ID_LITE` — 경량 모델 (briefing, verify)
- `GEMINI_FALLBACK_MODEL_ID` — 폴백 (기본: gemini-3.0-flash)
- `CLOUD_RUN_CAPTION_URLS` — 영상 업로드 서비스 URL (콤마 구분)

## Key Dependencies

- **FastAPI** + **uvicorn** — API 서버
- **google-genai** — Gemini API (Function Calling)
- **dependency-injector** — DI 컨테이너
- **prometheus-fastapi-instrumentator** — 메트릭 (`/metrics`)

## Notes

- 모든 프롬프트와 출력은 한국어 (X-Country-Code 헤더로 영어 지원)
- Docker: `docker/Dockerfile` + `docker/docker-compose.prod.yml`, `cheftory_network` 외부 네트워크 사용
