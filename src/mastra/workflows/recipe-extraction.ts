import { createWorkflow, createStep } from "@mastra/core/workflows";
import { z } from "zod";
import { google } from "@ai-sdk/google";
import { generateText } from "ai";
import { YoutubeTranscript } from "youtube-transcript";
import { phase4Prompt } from "../tools/analyze-video";

// ─── 유틸 ───

function msToTimestamp(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(
    2,
    "0"
  );
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

function extractVideoId(url: string): string | null {
  const patterns = [
    /(?:youtube\.com\/watch\?v=)([^&\s]+)/,
    /(?:youtu\.be\/)([^?\s]+)/,
    /(?:youtube\.com\/embed\/)([^?\s]+)/,
    /(?:youtube\.com\/shorts\/)([^?\s]+)/,
  ];
  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match) return match[1];
  }
  return null;
}

function normalizeUrl(url: string): string {
  const videoId = extractVideoId(url);
  return videoId ? `https://www.youtube.com/watch?v=${videoId}` : url;
}

function cleanJson(text: string): string {
  return text
    .replace(/```json\n?/g, "")
    .replace(/```\n?/g, "")
    .trim();
}

// ─── 프롬프트 ───

const phase1Prompt = `당신은 YouTube 요리 영상의 시각적 장면을 시간 순서대로 분석하는 전문가입니다.
모든 출력은 반드시 **한국어**로 작성하세요.

## 작업
영상을 처음부터 끝까지 시청하고, **화면에 보이는 조리 동작**을 시간 순서대로 나열하세요.
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
- ingredients: 화면에 보이는 재료 (cooking 타입인 경우, 한국어)
  - **화면에 재료의 분량이 텍스트(자막, 캡션, 오버레이 등)로 표시되어 있으면 분량도 함께 기록하세요.**
  - 예: 화면에 "간장 2큰술"이라고 텍스트가 보이면 → "간장 2큰술"
  - 텍스트가 없으면 재료명만 기록
- tools: 화면에 보이는 도구 (cooking 타입인 경우, 한국어)

## 중요 규칙
- 시간은 반드시 오름차순
- cooking 이벤트는 **최대한 세밀하게** 분리하세요. 하나의 동작 = 하나의 이벤트.
  - 예: "마늘을 칼등으로 으깨기" + "마늘을 다지기" = 2개의 이벤트
  - 예: "올리브유 붓기" + "마늘 넣기" = 2개의 이벤트
  - 5초 이상 지속되는 이벤트가 여러 동작을 포함하면 반드시 분리
- 화면에 보이는 것만 기록. 추측하지 마세요.
- non_cooking 이벤트도 빠짐없이 기록 (나중에 필터링용)

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

const phase2Prompt = `당신은 요리 영상 데이터를 분석하여 구조화된 레시피를 만드는 전문가입니다.

## 입력
3가지 데이터를 받습니다:
1. **자막**: 화자가 말한 내용 + 시간 (가장 신뢰도 높음)
2. **더보기란**: 크리에이터가 작성한 영상 설명 (재료/분량이 있을 수 있음)
3. **시각 분석**: 화면에 보이는 조리 동작 + 시간

## 작업

### 재료 추출 우선순위
1. **더보기란**에 재료 목록이 있으면 → 가장 높은 우선순위로 사용 (분량 포함)
2. **시각 분석**에서 화면에 텍스트로 표시된 재료/분량 → 보충
3. **자막**에서 분량 언급 → 보충
4. 시각 분석에서 화면에 명확히 식별 가능한 재료만 추가 (추측 금지. 예: 갈색 액체가 보인다고 간장이라고 추측하지 마세요)
5. 재료명은 범용적인 이름으로 통일 (브랜드명/제품명 제거)
   - "오늘좋은 3분 완성 스파게티" → "스파게티면"
   - "오늘좋은 엑스트라버진 올리브유" → "올리브유"
   - "다진 마늘" + "마늘" → "마늘"로 통합 (손질 상태는 step description에서 설명)

### step 구성 규칙
1. **시각 분석의 cooking 이벤트를 시간순으로** step으로 그룹핑합니다.
2. intro, outro, non_cooking 이벤트는 제외합니다.
3. 연속으로 이어지는 cooking 동작은 하나의 step으로 묶습니다.
4. 시간적으로 떨어져 있으면 별도 step으로 분리합니다.
5. **플레이팅(접시에 담기)은 반드시 별도 step으로 분리합니다.**
   - 조리 완료 후 접시에 옮겨 담는 동작이 나오면 이전 조리 step과 분리하세요.
   - 플레이팅 후 토핑/가니쉬를 올리는 동작은 플레이팅 step에 포함합니다.
   - 잘못된 예: "주걱을 사용해 완성된 파스타를 접시에 올려두고, 추가로 다진 마늘을 올려 섞어주세요." (조리와 플레이팅이 하나의 step)
   - 올바른 예: 조리 step / 플레이팅 step ("접시에 파스타를 담고 다진 마늘을 올려주세요.")으로 분리
6. **하나의 step에 description이 4개를 초과하면 반드시 분할합니다.**
   - description 항목이 5개 이상이면 내용 기준으로 2개 이상의 step으로 나누어 각 step이 4개 이하가 되도록 하세요.
   - 분할된 각 step의 title은 해당 step의 실제 조리 내용을 반영하세요.
   - 잘못된 예: "재료 손질 (1)", "재료 손질 (2)" — 번호 붙이기 금지
   - 올바른 예: "마늘과 파슬리 다지기" / "페페론치노 씨 빼고 썰기" — 각 step의 내용이 제목에 드러나야 함
7. step 순서는 반드시 시간 오름차순.

### step title 작성 규칙
- 해당 step의 **조리 방법 + 맥락**을 간결하게 제목으로 사용
- 잘못된 예: "오일 소스 끓이기" → 올바른 예: "프라이팬에 오일소스로 볶기"
- 잘못된 예: "베이스 만들기" → 올바른 예: "올리브유에 마늘 볶기"
- 잘못된 예: "마무리 단계" → 올바른 예: "파슬리 넣고 면 섞기"
- 잘못된 예: "재료 손질" → 올바른 예: "마늘과 페페론치노 다지기"
- "~만들기", "~단계", "~준비" 같은 추상적 용어 사용 금지
- 실제로 어떻게 조리하는지가 드러나야 함

### description에 포함할 동작 / 제외할 동작
포함 (조리에 필요한 동작):
- 재료 손질: 썰기, 다지기, 껍질 벗기기, 싹 제거, 줄기 분리 등
- 조리: 볶기, 끓이기, 데치기, 삶기, 굽기 등
- 투입: 팬/냄비에 재료 넣기, 양념 넣기 등
- 양념/간: 소금, 후추 뿌리기, 간 맞추기 등
- 플레이팅: 접시에 담기, 토핑 올리기, 치즈 뿌리기 등

제외 (조리에 불필요한 동작):
- 포장 뜯기/개봉 (예: "파스타면 포장을 칼로 뜯어주세요")
- 도구 닦기/정리 (예: "키친타월로 올리브유 병 입구를 닦아주세요")
- 병뚜껑 열기/닫기
- 재료를 냉장고에서 꺼내기
- 도구 배치/세팅

### description 작성 규칙
- 각 소 단계는 { content, start } 형태의 배열.
- content: 하나의 재료에 대한 동작 = 하나의 문장.
  잘못된 예: "파슬리의 줄기와 잎을 분리하고, 마늘은 칼등으로 눌러줍니다."
  올바른 예: "파슬리의 줄기와 잎을 분리합니다." / "마늘은 칼등으로 눌러줍니다."
  단, 같은 재료의 연속 동작은 합칩니다.
  올바른 예: "파슬리의 줄기와 잎을 분리하고 냄비에 넣어줍니다."
- start: 해당 동작의 시작 시간 (시각 분석의 time 참조)
- 자막에서 화자가 사용한 표현을 그대로 사용 (의역 금지)
- "야채를 모두 넣어줍니다" 같은 뭉뚱그린 표현 절대 금지
- **분량 보충 (중요)**: "된장을 넣어주세요"처럼 분량 없이 재료를 투입하는 동작이 있으면, 아래 우선순위로 분량을 찾아 보충하세요.
  1. 더보기란에 해당 재료의 분량이 있으면 반영
  2. 시각 분석에서 화면 텍스트로 표시된 분량이 있으면 반영
  3. 자막에서 "한 숟가락", "두 스푼" 등의 언급이 있으면 반영
  - 어디에서도 분량을 알 수 없으면 description 텍스트는 그대로 두되, **해당 재료를 넣는 장면을 scenes에 추가하세요** (사용자가 영상에서 직접 양을 확인할 수 있도록).
    - 예: 분량을 알 수 없는 "된장을 넣어주세요" → scenes에 { "label": "된장 넣는 양", "start": "...", "end": "..." } 추가
  - 절대 분량을 지어내지 마세요

### tip 추출
- 자막에서 화자가 직접 말한 조리 팁만 추출
- "이렇게 하면 더 잘 돼요" 류의 실행 노하우
- 절대 지어내지 마세요
- **유튜버 고유 조리법 (매우 중요)**: 화자가 일반적인 방법과 비교하며 자신만의 방식을 권하는 경우, 반드시 tip으로 추출하세요.
  - 이 패턴은 보통 "일반적으로는 ~하잖아요/~하거든요. 근데 저는 ~하면 더 ~해요" 식의 비교 문장으로 나타납니다.
  - **description에 해당 조리법을 절대 빠뜨리지 마세요.** 유튜버가 특정 방식을 권했다면, 그 방식이 description에 반드시 포함되어야 합니다. 일반적인 방법이 아닌 유튜버가 권한 방법으로 작성하세요.
  - 예: "보통 마늘을 으깨서 넣잖아요. 근데 슬라이스해서 넣으면 식감이 더 살아요"
    → tip: "마늘을 으깨지 말고 슬라이스하면 식감이 더 살아요"
    → description에 "마늘을 슬라이스해주세요"가 반드시 포함 (으깨기로 적으면 안 됨, 빠뜨려도 안 됨)
  - 예: "원래 센 불에서 볶는데, 약불에서 천천히 볶으면 마늘이 안 타요"
    → tip: "약불에서 천천히 볶으면 마늘이 타지 않아요"
    → description에 약불 기준으로 반드시 포함

### knowledge 추출
- 자막에서 화자가 직접 말한 배경지식/원리만 추출
- "왜 그런지" 류의 설명
- 절대 지어내지 마세요

### 맛있게 먹는 팁 (servingTip)
- 자막에서 화자가 맛있게 먹는 방법을 언급한 경우에만 추출
- 없으면 null

## 출력
JSON으로만 응답하세요. JSON 외 텍스트 없이.

{
  "title": "string (자막/영상에서 소개하는 실제 요리 이름)",
  "description": "string | null",
  "servings": "number | null",
  "cookingTimeMinutes": "number | null",
  "difficulty": "쉬움 | 보통 | 어려움",
  "category": "string",
  "ingredients": [
    { "name": "string", "amount": { "value": "number | null", "unit": "string | null" }, "substitute": "string | null", "selectionTip": "string | null" }
  ],
  "tools": [{ "name": "string" }],
  "steps": [
    {
      "order": "number",
      "title": "string",
      "description": [
        { "content": "string", "start": "HH:MM:SS" }
      ],
      "tip": "string | string[] | null",
      "knowledge": "string | null",
      "timerSeconds": "number | null"
    }
  ],
  "servingTip": "string | null"
}`;

const phase3Prompt = `당신은 요리 레시피의 품질을 검증하고 수정하는 전문가입니다.

## 입력
생성된 레시피 JSON을 받습니다.

## 검증 및 수정 항목

### 1. 말투 통일 (가장 중요)
모든 description의 content를 **레시피 지시문 말투**로 통일하세요.
- 잘못된 예 (설명/나레이션체): "팬에 올리브유를 붓고 있습니다.", "마늘을 다지고 있습니다."
- 올바른 예 (지시문체): "팬에 올리브유를 넉넉하게 부어주세요.", "마늘을 잘게 다져주세요."
- "~합니다", "~있습니다" → "~해주세요", "~하세요"로 변환
- 단, 분량이나 구체적 동작 정보는 유지

### 2. 재료명 정규화
- 브랜드명/세부 종류를 범용 이름으로 변경 (description 내에서만)
  - "엑스트라버진 올리브유" → "올리브유"
  - "3분 완성 스파게티면" → "스파게티면"
  - "칙필레 소스" → 고유 제품이므로 그대로 유지
- ingredients 배열의 name은 원본 유지 (정확한 제품명이 필요할 수 있으므로)
- description의 content에서만 범용 이름 사용

### 3. 중복 제거
- 같은 동작이 중복된 description content 제거
  - 예: "다진 마늘을 팬에 넣습니다" + "다진 마늘을 팬에 추가로 넣습니다" → 하나로 합치기

### 4. 시간순서 검증
- steps의 order가 시간 오름차순인지 확인
- description 내 start가 오름차순인지 확인
- 어긋나면 올바른 순서로 재배치

### 5. 빈값 정리
- tip이 null이면 필드 자체를 null로 유지
- knowledge가 null이면 필드 자체를 null로 유지
- 빈 배열 []이면 null로 변환

## 출력
수정된 레시피 JSON을 그대로 출력하세요. JSON 외 텍스트 없이.
입력과 동일한 JSON 스키마를 유지하세요.`;

const phase5Prompt = `당신은 요리 레시피를 보완하는 전문가입니다.

## 입력
1. **레시피 JSON**: 기존 레시피
2. **시각 분석 데이터**: 영상의 조리 동작 시간 정보
3. **피드백**: 초보 요리사가 이해하기 어렵다고 지적한 부분들

## 작업

### 1. 텍스트 가독성 개선
피드백의 textImprovement를 참고하여, 해당 description content를 더 명확하게 수정하세요.
- 원본의 의미와 화자 표현은 최대한 유지
- 모호한 부분만 구체적으로 보충

### 2. 장면(scenes) 추가
피드백에서 needsScene이 true인 항목만, 해당 step에 scenes 배열을 추가하세요.
- 시각 분석 데이터에서 해당 동작과 가장 일치하는 시간을 찾아 start/end를 매핑
- needsScene이 false인 항목은 텍스트 개선만 적용하고 장면은 추가하지 마세요
- scenes 형식: [{ "label": "string", "start": "HH:MM:SS", "end": "HH:MM:SS" }]

### 3. 장면이 필요 없는 step
피드백에 없는 step이나 needsScene이 모두 false인 step은 scenes를 null로 설정하세요.

### 4. 최소 장면 보장
피드백에 needsScene: true인 항목이 하나도 없더라도, 전체 레시피에서 가장 핵심적인 조리 동작 1개를 골라 장면을 추가하세요.
- 시각 분석 데이터에서 가장 중요한 cooking 이벤트를 선택
- 레시피 전체에 scenes가 0개인 상태로 완성하지 마세요

## 출력
보완된 레시피 JSON을 그대로 출력하세요. JSON 외 텍스트 없이.
기존 스키마에 scenes 필드가 추가된 형태입니다.

steps 내 스키마:
{
  "order": "number",
  "title": "string",
  "description": [{ "content": "string", "start": "HH:MM:SS" }],
  "tip": "string | string[] | null",
  "knowledge": "string | null",
  "scenes": [{ "label": "string", "start": "HH:MM:SS", "end": "HH:MM:SS" }] | null,
  "timerSeconds": "number | null"
}`;

// ─── Step 1: 데이터 수집 (자막 + 더보기란 + 시각분석 병렬) ───

const collectDataStep = createStep({
  id: "collect-data",
  description: "YouTube 영상에서 자막, 더보기란, 시각 분석 데이터를 병렬로 수집합니다.",
  inputSchema: z.object({
    url: z.string(),
  }),
  outputSchema: z.object({
    subtitles: z.string(),
    videoTitle: z.string(),
    channelName: z.string(),
    videoDescription: z.string(),
    visualAnalysis: z.string(),
  }),
  execute: async ({ inputData }) => {
    const url = normalizeUrl(inputData.url);
    console.log("[Step 1] 데이터 수집 시작 (병렬)...");

    const [subtitles, videoInfo, visualResult] = await Promise.all([
      // 자막
      (async () => {
        try {
          const transcript = await YoutubeTranscript.fetchTranscript(url, {
            lang: "ko",
          });
          return transcript.map((entry) => ({
            start: msToTimestamp(entry.offset),
            end: msToTimestamp(entry.offset + entry.duration),
            text: entry.text,
          }));
        } catch {
          try {
            const transcript = await YoutubeTranscript.fetchTranscript(url);
            return transcript.map((entry) => ({
              start: msToTimestamp(entry.offset),
              end: msToTimestamp(entry.offset + entry.duration),
              text: entry.text,
            }));
          } catch {
            return [];
          }
        }
      })(),

      // 더보기란
      (async () => {
        const videoId = extractVideoId(url);
        if (!videoId) return { description: "", title: "", channelName: "" };
        try {
          const oembedRes = await fetch(
            `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`
          );
          const oembedData = (await oembedRes.json()) as {
            title: string;
            author_name: string;
          };
          const pageRes = await fetch(
            `https://www.youtube.com/watch?v=${videoId}`,
            {
              headers: {
                "User-Agent":
                  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept-Language": "ko-KR,ko;q=0.9",
              },
            }
          );
          const html = await pageRes.text();
          let description = "";
          const shortDescMatch = html.match(
            /"shortDescription":"((?:[^"\\]|\\.)*)"/
          );
          if (shortDescMatch) {
            description = shortDescMatch[1]
              .replace(/\\n/g, "\n")
              .replace(/\\"/g, '"')
              .replace(/\\\\/g, "\\");
          }
          if (!description) {
            const metaMatch = html.match(
              /<meta\s+name="description"\s+content="([^"]*?)"/
            );
            if (metaMatch) description = metaMatch[1];
          }
          return {
            description,
            title: oembedData.title || "",
            channelName: oembedData.author_name || "",
          };
        } catch {
          return { description: "", title: "", channelName: "" };
        }
      })(),

      // 시각 분석 (Gemini)
      generateText({
        model: google("gemini-3.1-flash-lite-preview"),
        messages: [
          {
            role: "user",
            content: [
              { type: "file", data: url, mediaType: "video/mp4" },
              { type: "text", text: phase1Prompt },
            ],
          },
        ],
      }),
    ]);

    console.log(
      `[Step 1 완료] 자막: ${subtitles.length}개, 더보기란: ${videoInfo.description.length}자`
    );

    return {
      subtitles: JSON.stringify(subtitles),
      videoTitle: videoInfo.title,
      channelName: videoInfo.channelName,
      videoDescription: videoInfo.description,
      visualAnalysis: visualResult.text,
    };
  },
});

// ─── Step 2: 레시피 구조화 (scenes 없음) ───

const structureRecipeStep = createStep({
  id: "structure-recipe",
  description: "수집된 데이터를 기반으로 레시피 JSON을 구조화합니다.",
  inputSchema: z.object({
    subtitles: z.string(),
    videoTitle: z.string(),
    channelName: z.string(),
    videoDescription: z.string(),
    visualAnalysis: z.string(),
  }),
  outputSchema: z.object({
    rawRecipe: z.string(),
    visualAnalysis: z.string(),
  }),
  execute: async ({ inputData }) => {
    console.log("[Step 2] 레시피 구조화 시작...");

    const combinedInput = `## 자막 데이터 (화자가 말한 내용)
${inputData.subtitles}

## 더보기란 데이터
영상 제목: ${inputData.videoTitle}
채널: ${inputData.channelName}
설명:
${inputData.videoDescription}

## 시각 분석 데이터 (화면에 보이는 조리 동작)
${inputData.visualAnalysis}`;

    const result = await generateText({
      model: google("gemini-3.1-flash-lite-preview"),
      messages: [
        {
          role: "user",
          content: `${combinedInput}\n\n${phase2Prompt}`,
        },
      ],
    });

    console.log("[Step 2 완료] 레시피 초안 생성됨");
    return {
      rawRecipe: cleanJson(result.text),
      visualAnalysis: inputData.visualAnalysis,
    };
  },
});

// ─── Step 3: 검증 및 수정 ───

const validateRecipeStep = createStep({
  id: "validate-recipe",
  description: "생성된 레시피를 검증하고 말투/재료명/순서를 수정합니다.",
  inputSchema: z.object({
    rawRecipe: z.string(),
    visualAnalysis: z.string(),
  }),
  outputSchema: z.object({
    validatedRecipe: z.string(),
    visualAnalysis: z.string(),
  }),
  execute: async ({ inputData }) => {
    console.log("[Step 3] 검증 및 수정 시작...");

    const result = await generateText({
      model: google("gemini-3.1-flash-lite-preview"),
      messages: [
        {
          role: "user",
          content: `아래 레시피 JSON을 검증하고 수정해주세요.\n\n${inputData.rawRecipe}\n\n${phase3Prompt}`,
        },
      ],
    });

    console.log("[Step 3 완료] 검증 및 수정 완료");
    return {
      validatedRecipe: cleanJson(result.text),
      visualAnalysis: inputData.visualAnalysis,
    };
  },
});

// ─── Step 4: 초보 요리사 피드백 ───

const feedbackStep = createStep({
  id: "cook-feedback",
  description: "초보 요리사 시점으로 레시피를 검토하고 이해 안 되는 부분과 필요한 장면을 피드백합니다.",
  inputSchema: z.object({
    validatedRecipe: z.string(),
    visualAnalysis: z.string(),
  }),
  outputSchema: z.object({
    validatedRecipe: z.string(),
    visualAnalysis: z.string(),
    feedback: z.string(),
  }),
  execute: async ({ inputData }) => {
    console.log("[Step 4] 초보 요리사 시점으로 레시피 검토 중...");

    const result = await generateText({
      model: google("gemini-3.1-flash-lite-preview"),
      messages: [
        {
          role: "user",
          content: `아래 레시피를 읽고 이해하기 어려운 부분과 필요한 장면을 알려주세요.\n\n${inputData.validatedRecipe}\n\n${phase4Prompt}`,
        },
      ],
    });

    console.log("[Step 4 완료] 피드백 도출됨");
    return {
      validatedRecipe: inputData.validatedRecipe,
      visualAnalysis: inputData.visualAnalysis,
      feedback: cleanJson(result.text),
    };
  },
});

// ─── Step 5: 피드백 기반 보완 (텍스트 개선 + 장면 추가) ───

const enhanceRecipeStep = createStep({
  id: "enhance-recipe",
  description: "피드백을 기반으로 레시피 가독성을 개선하고 필요한 장면을 추가합니다.",
  inputSchema: z.object({
    validatedRecipe: z.string(),
    visualAnalysis: z.string(),
    feedback: z.string(),
  }),
  outputSchema: z.object({
    recipe: z.string(),
  }),
  execute: async ({ inputData }) => {
    console.log("[Step 5] 피드백 기반으로 레시피 보완 중...");

    const phase5Input = `## 레시피 JSON
${inputData.validatedRecipe}

## 시각 분석 데이터
${inputData.visualAnalysis}

## 피드백
${inputData.feedback}`;

    const result = await generateText({
      model: google("gemini-3.1-flash-lite-preview"),
      messages: [
        {
          role: "user",
          content: `${phase5Input}\n\n${phase5Prompt}`,
        },
      ],
    });

    console.log("[Step 5 완료] 레시피 보완 완료");
    return { recipe: cleanJson(result.text) };
  },
});

// ─── Workflow ───

export const recipeExtractionWorkflow = createWorkflow({
  id: "recipe-extraction",
  description: "YouTube 요리 영상에서 구조화된 레시피를 추출하는 워크플로우",
  inputSchema: z.object({
    url: z.string(),
  }),
  outputSchema: z.object({
    recipe: z.string(),
  }),
})
  .then(collectDataStep)
  .then(structureRecipeStep)
  .then(validateRecipeStep)
  .then(feedbackStep)
  .then(enhanceRecipeStep);

recipeExtractionWorkflow.commit();
