/**
 * Ground Truth 데이터 수집 스크립트
 *
 * 각 테스트 영상의 원본 데이터(자막, 더보기란, 시각 분석)를 수집하여
 * fixtures/ 폴더에 JSON으로 저장합니다.
 *
 * 실행: npx tsx src/mastra/evals/collect-ground-truth.ts
 */

import "dotenv/config";
import { writeFileSync, existsSync } from "fs";
import { join } from "path";
import { google } from "@ai-sdk/google";
import { generateText } from "ai";
import {
  fetchSubtitles,
  fetchDescription,
  extractVideoId,
} from "../tools/analyze-video";
import { evalDataset } from "./dataset";

const FIXTURES_DIR = join(__dirname, "fixtures");

/**
 * Ground Truth 전용 시각 분석 프롬프트
 * - 에이전트용(phase1Prompt)보다 훨씬 세밀한 1초 단위 분석
 * - Gemini 3.1 Pro로 실행하여 정확한 정답 기준 생성
 */
const groundTruthVisualPrompt = `당신은 YouTube 요리 영상의 시각적 장면을 **초 단위로 정밀 분석**하는 전문가입니다.
모든 출력은 반드시 **한국어**로 작성하세요.

## 작업
영상을 처음부터 끝까지 **1초씩** 확인하고, **화면에 보이는 조리 동작**을 시간 순서대로 나열하세요.
화자가 말하는 내용은 별도로 제공되므로, 당신은 **눈에 보이는 것만** 기록하세요.

## 타임스탬프 규칙 (매우 중요)
- 형식: HH:MM:SS (시:분:초)
- 예시: 영상 1분 3초 → "00:01:03" (절대 "01:03:00"이 아님)
- 예시: 영상 15초 → "00:00:15"
- 예시: 영상 2분 30초 → "00:02:30"
- 첫 번째 자리는 "시간"입니다. 10분 이하 영상에서 첫 자리가 "01" 이상이면 잘못된 것입니다.

## 각 이벤트에 포함할 정보
- time: 동작 시작 시간 (HH:MM:SS)
- endTime: 동작 끝 시간 (HH:MM:SS)
- type: 이벤트 유형
  - "cooking": 실제 조리 동작 (썰기, 볶기, 넣기, 뒤집기 등)
  - "intro": 인트로/오프닝
  - "outro": 아웃트로/엔딩
  - "non_cooking": 토킹, 광고, 자막만 나오는 화면 등
- visual: 화면에서 보이는 동작을 **한국어로** 구체적으로 설명
  - 어떤 재료가, 어떤 도구로, 어떻게 다뤄지는지
  - 칼질 방식(다지기, 슬라이스, 편 썰기 등)이 보이면 정확히 기술
  - 재료의 색, 크기, 질감 변화가 보이면 상세히 기록
- ingredients: 화면에 보이는 재료 (cooking 타입인 경우, 한국어)
  - **화면에 재료의 분량이 텍스트(자막, 캡션, 오버레이 등)로 표시되어 있으면 분량도 함께 기록하세요.**
  - 예: 화면에 "간장 2큰술"이라고 텍스트가 보이면 → "간장 2큰술"
  - 텍스트가 없으면 재료명만 기록
- tools: 화면에 보이는 도구 (cooking 타입인 경우, 한국어)

## ★★★ cooking 이벤트 분리 규칙 (가장 중요 — 이 규칙을 어기면 전체 출력이 무효) ★★★

**cooking 이벤트 1개 = 정확히 1초 (time과 endTime의 차이가 1초)**

모든 cooking 이벤트는 반드시 1초 단위로 기록하세요.
- time: "00:01:05", endTime: "00:01:06" → ✅ 올바름 (1초)
- time: "00:01:05", endTime: "00:01:08" → ❌ 틀림 (3초, 분할 필수)

### 방법
영상의 매 초마다 화면을 확인하고, 해당 1초 동안 보이는 cooking 동작을 기록하세요.
- 00:03:05~00:03:06: "칼로 마늘을 얇게 슬라이스하는 중"
- 00:03:06~00:03:07: "슬라이스한 마늘을 칼등으로 모으는 중"
- 00:03:07~00:03:08: "다진 마늘을 그릇에 옮기는 중"

### 같은 동작이 여러 초 계속될 경우
동일한 동작이 지속되어도 **1초마다 별도 이벤트**로 기록하세요.
- 00:02:00~00:02:01: "양파를 채 썰기 중"
- 00:02:01~00:02:02: "양파를 채 썰기 계속"
- 00:02:02~00:02:03: "양파를 채 썰기 계속"
- 00:02:03~00:02:04: "양파 채 썰기 마무리"

### 잘못된 예 (절대 이렇게 하지 마세요)
\`\`\`
❌ { "time": "00:01:12", "endTime": "00:01:25", "visual": "마른 멸치의 머리와 내장을 손으로 떼어내어 손질함." }
→ 13초짜리 단일 이벤트. 반드시 13개의 1초 이벤트로 분할.
\`\`\`

### 올바른 예
\`\`\`
✅ { "time": "00:01:12", "endTime": "00:01:13", "visual": "첫 번째 멸치를 손으로 집음" }
✅ { "time": "00:01:13", "endTime": "00:01:14", "visual": "멸치 머리를 손가락으로 뜯어냄" }
✅ { "time": "00:01:14", "endTime": "00:01:15", "visual": "멸치 내장(검은 부분)을 긁어냄" }
✅ { "time": "00:01:15", "endTime": "00:01:16", "visual": "두 번째 멸치를 집어 머리를 뜯음" }
... (매 초마다 계속)
\`\`\`

## non_cooking 이벤트 규칙
- non_cooking은 길어도 괜찮습니다 (토킹, 설명 등은 합쳐도 됨)
- 하지만 cooking 이벤트는 **절대 3초를 초과하지 마세요**

## 기타 규칙
- 시간은 반드시 오름차순
- 화면에 보이는 것만 기록. 추측하지 마세요.
- non_cooking 이벤트도 빠짐없이 기록 (나중에 필터링용)
- **화면에 보이는 텍스트(자막, 오버레이, 캡션)는 모두 기록하세요.**

## 출력
JSON 배열로만 응답하세요. JSON 외 텍스트 없이.

[
  {
    "time": "HH:MM:SS",
    "endTime": "HH:MM:SS",
    "type": "cooking | intro | outro | non_cooking",
    "visual": "string (한국어)",
    "ingredients": ["string (한국어)"] | null,
    "tools": ["string (한국어)"] | null
  }
]`;

/** 저장되는 ground truth 형식 */
export interface GroundTruth {
  name: string;
  url: string;
  videoId: string;
  collectedAt: string;
  subtitles: Array<{ start: string; end: string; text: string }>;
  videoInfo: { description: string; title: string; channelName: string };
  visualAnalysis: {
    raw: string;
    parsed: Array<{
      time: string;
      endTime: string;
      type: string;
      visual: string;
      ingredients: string[] | null;
      tools: string[] | null;
    }> | null;
  };
}

async function collectOne(
  entry: (typeof evalDataset)[0]
): Promise<GroundTruth> {
  const videoId = extractVideoId(entry.url) ?? "unknown";
  const normalizedUrl = `https://www.youtube.com/watch?v=${videoId}`;

  console.log(`${Date.now()}  📡 자막 + 더보기 + 시각분석 병렬 수집 중...`);

  const [subtitles, videoInfo, phase1Result] = await Promise.all([
    fetchSubtitles(normalizedUrl),
    fetchDescription(normalizedUrl),
    generateText({
      model: google("gemini-3.1-pro-preview"),
      messages: [
        {
          role: "user",
          content: [
            { type: "file", data: normalizedUrl, mediaType: "video/mp4" },
            { type: "text", text: groundTruthVisualPrompt },
          ],
        },
      ],
      onFinish:()=>{
        console.log("영상 분석 완료");
      }
    }),
  ]);

  // 시각 분석 JSON 파싱 시도
  const rawVisual = phase1Result.text;
  let parsedVisual = null;
  try {
    const cleaned = rawVisual
      .replace(/```json\n?/g, "")
      .replace(/```\n?/g, "")
      .trim();
    parsedVisual = JSON.parse(cleaned);
  } catch {
    // 파싱 실패 시 raw만 저장
  }

  return {
    name: entry.name,
    url: entry.url,
    videoId,
    collectedAt: new Date().toISOString(),
    subtitles,
    videoInfo,
    visualAnalysis: {
      raw: rawVisual,
      parsed: parsedVisual,
    },
  };
}

async function main() {
  // EVAL_LIMIT 환경변수로 수집 개수 제한 (기본: 전체)
  const limit = Number(process.env.EVAL_LIMIT) || evalDataset.length;
  const dataset = evalDataset.slice(0, limit);

  // 처리할 항목 필터 (이미 수집된 건 스킵)
  const toCollect = dataset.filter((entry) => {
    const videoId = extractVideoId(entry.url) ?? "unknown";
    const filePath = join(FIXTURES_DIR, `${videoId}.json`);
    if (existsSync(filePath)) {
      console.log(`⏭️  [${entry.name}] 이미 수집됨 — 스킵`);
      return false;
    }
    else{
      console.log(`⏭️  [${entry.name}] [${entry.url}] 수집 필요`);
    }
    return true;
  });

  console.log(
    `\n📦 총 ${dataset.length}개 중 ${toCollect.length}개 수집 필요\n`
  );

  // 동시 3개씩 병렬 처리 (Gemini API 부하 제한)
  const CONCURRENCY = 2;
  for (let i = 0; i < toCollect.length; i += CONCURRENCY) {
    const batch = toCollect.slice(i, i + CONCURRENCY);

    const results = await Promise.allSettled(
      batch.map(async (entry) => {
        const videoId = extractVideoId(entry.url) ?? "unknown";
        console.log(
          `\n🎬 [${i + batch.indexOf(entry) + 1}/${toCollect.length}] ${entry.name}`
        );

        const data = await collectOne(entry);

        const filePath = join(FIXTURES_DIR, `${videoId}.json`);
        writeFileSync(filePath, JSON.stringify(data, null, 2), "utf-8");
        console.log(`  ✅ 저장 완료 → fixtures/${videoId}.json`);
        console.log(
          `     자막: ${data.subtitles.length}개, 더보기: ${data.videoInfo.description.length}자, 시각이벤트: ${data.visualAnalysis.parsed?.length ?? "파싱실패"}개`
        );

        return data;
      })
    );

    // 실패 로그
    for (const r of results) {
      if (r.status === "rejected") {
        console.error();
        console.error(`  ❌ 실패:`, r.reason?.message ?? r.reason);
      }
    }
  }

  console.log(`\n🏁 수집 완료!`);
}

main().catch(console.error);
