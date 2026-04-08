# step.video_summarize v2

**Date:** 2026-04-08
**Based on:** v1

## Why
1. v1은 step 순서가 영상 등장 순서를 따라야 한다는 규칙이 약했다 — `Sort groups in ascending time order`
   한 줄뿐이라, 모델이 "논리적 조리 흐름"으로 재배열하는 것을 막지 못했다.
2. v1의 `start` 필드 정의가 모호해서, 자막에 등장하는 duration("10분간 끓이세요")을
   `00:10:00`처럼 timestamp로 잘못 변환할 여지가 있었다.

## Changes
- 새 섹션 `[Order Constraint (Critical)]` 추가
  - 영상 등장 순서를 step 순서로 강제
  - "logical cooking flow"를 위한 재배열 금지
  - 플래시백/인서트 컷도 화면에 등장한 시각에 배치
  - 시간 동률 시 화면 등장 순으로 break tie
  - 나중 등장 동작을 앞 동작 앞에 두는 것 금지
- `[Timecode Rules]` 강화
  - `start`를 "absolute video playback timestamp (영상 시작 00:00:00 기준)"로 명시
  - 안티 예시 추가: "boil for 10 minutes" 같은 자막 duration → `00:10:00` 금지
  - 영상 총 길이를 넘는 timestamp 금지
  - step 간 / 같은 step 내 description 간 monotonic non-decreasing 강제

## Expected impact
- `StepChronologicalOrder` 결정적 메트릭 점수 상승 (사실상 1.0이 기본값이 되어야 함)
- `StepTimestampAccuracy` (GT 기반, tolerance 2초) 점수 개선 — duration/timestamp 혼동 케이스 감소
- 일부 영상에서 step 분할이 살짝 더 세분화될 수 있음 (등장 순서를 무리하게 따르려는 부작용)

## Risks / things to watch
- 시간을 거슬러 보여주는 편집(ASMR, 스타일 영상)에서 부자연스러운 step 순서 가능성
- 평가 데이터셋에 그런 케이스가 있다면 별도 트랙으로 분리 검토
- 매우 짧은 영상에서 over-splitting 회귀 — `StepQuality` 메트릭으로 모니터링
