import {
  type ParsedRecipe,
  type ClassifierChoice,
  type GTEvent,
  timestampToSeconds,
  getAllScenes,
  getCookingEvents,
  geminiClassifier,
  withRetry,
} from "./helpers";
import type { GroundTruth } from "../collect-ground-truth";

// ─── SceneTimestampAccuracy (LLM per scene) ───

const SCENE_RELEVANCE_PROMPT = `당신은 요리 영상 분석 전문가입니다.

## 작업
아래에 레시피에서 추출된 "장면 라벨"과, 해당 시간대에 실제로 영상에서 보이는 "조리 동작 목록"이 있습니다.
장면 라벨이 실제 조리 동작과 관련이 있는지 판단하세요.

## 판단 기준
- 장면 라벨이 설명하는 동작/재료가 실제 조리 동작 목록에 포함되어 있는가?
- 라벨: "마늘 편썰기" / 동작: "마늘을 칼로 얇게 슬라이스" → 관련 있음 (A)
- 라벨: "마늘 편썰기" / 동작: "양파를 채 썰기" → 관련 없음 (D)
- 라벨의 핵심 재료/동작이 조리 동작에 전혀 언급되지 않으면 관련 없음

## 장면 라벨
{{output}}

## 해당 시간대의 실제 조리 동작
{{expected}}`;

const SCENE_RELEVANCE_SCORES: ClassifierChoice = {
  A: 1.0,
  B: 0.7,
  C: 0.3,
  D: 0.0,
};

export async function scoreSceneTimestampAccuracy(
  recipe: ParsedRecipe | null,
  gt: GroundTruth | null
): Promise<{ score: number; details: string[] }> {
  const scenes = getAllScenes(recipe);
  const cookingEvents = getCookingEvents(gt);
  if (scenes.length === 0) return { score: 1, details: ["scene 없음 — 패널티 없음"] };
  if (cookingEvents.length === 0) return { score: 1, details: ["GT cooking 없음 — 패널티 없음"] };

  let totalScore = 0;
  const details: string[] = [];

  for (const scene of scenes) {
    const sceneStart = timestampToSeconds(scene.start);
    const sceneEnd = timestampToSeconds(scene.end);

    const overlapping = cookingEvents.filter((evt) => {
      const evtStart = timestampToSeconds(evt.time);
      const evtEnd = timestampToSeconds(evt.endTime);
      return evtStart >= sceneStart && evtEnd <= sceneEnd;
    });

    if (overlapping.length === 0) {
      details.push(`"${scene.label}" (${scene.start}~${scene.end}): GT 이벤트 없음`);
      continue;
    }

    const gtDescription = overlapping
      .map((evt) => {
        const parts = [evt.visual];
        if (evt.ingredients) parts.push(`재료: ${evt.ingredients.join(", ")}`);
        if (evt.tools) parts.push(`도구: ${evt.tools.join(", ")}`);
        return `[${evt.time}] ${parts.join(" / ")}`;
      })
      .join("\n");

    const result = await withRetry(() =>
      geminiClassifier(
        SCENE_RELEVANCE_PROMPT,
        scene.label,
        gtDescription,
        SCENE_RELEVANCE_SCORES,
        false
      )
    );

    const sceneScore = result.score ?? 0;
    totalScore += sceneScore;
    if (sceneScore < 0.5) {
      details.push(
        `"${scene.label}" (${scene.start}~${scene.end}): ${sceneScore}점 — GT: ${overlapping[0].visual.slice(0, 40)}`
      );
    }
  }

  return { score: scenes.length > 0 ? totalScore / scenes.length : 0, details };
}

// ─── SceneCoverage (LLM 1회) ───

export const SCENE_COVERAGE_PROMPT = `당신은 요리를 많이 해보지 않은 20대 초보 요리사입니다.
계란 프라이, 라면 끓이기, 밥 짓기 같은 기본적인 요리는 할 수 있지만, 특수한 재료 손질이나 전문 조리 기법은 모릅니다.
아래 레시피의 각 단계(step)를 읽고, 장면(scene) 배치가 적절한지 평가하세요.

## 판단 기준
**"이 동작을 잘못하면 요리가 실패하는데, 텍스트만 읽고 올바르게 할 수 있는가?"**

장면이 필요한 경우 — 다음 두 조건을 **모두** 만족:
1. 잘못하면 요리 결과가 크게 달라지거나 실패할 수 있는 동작
2. 텍스트만 읽고는 정확한 그림이 안 그려지는 동작

장면이 불필요한 경우 — 다음 중 **하나라도** 해당:
- 텍스트에 수치/분량이 명시되어 영상 없이도 정확히 할 수 있는 동작
- 텍스트만 읽어도 방법이 명확한 단순한 동작

**누락이 과도보다 심각합니다.**
- 필요한 곳에 없으면(누락) → 큰 감점
- 불필요한 곳에 있으면(과도) → 작은 감점

## 평가 기준
**누락이 과도보다 심각합니다.**
- 필요한 곳에 없으면(누락) → 초보자가 막혀서 요리 실패 → 큰 감점
- 불필요한 곳에 있으면(과도) → 약간 번거롭지만 요리는 가능 → 작은 감점

## 레시피
{{output}}

## 영상 원본 데이터 (참고)
{{expected}}`;

export const SCENE_COVERAGE_SCORES: ClassifierChoice = {
  A: 1.0,
  B: 0.7,
  C: 0.4,
  D: 0.15,
  E: 0.0,
};

// ─── SceneLabelConciseness (규칙) ───

export function scoreSceneLabelConciseness(recipe: ParsedRecipe | null): number {
  const scenes = getAllScenes(recipe);
  if (scenes.length === 0) return 1; // scene 없으면 패널티 없음

  let total = 0;
  for (const scene of scenes) {
    const len = scene.label.length;
    if (len >= 3 && len <= 12) total += 1.0;
    else if (len >= 2 && len <= 15) total += 0.6;
    else if (len > 15) total += 0.1;
    else total += 0.2;
  }

  return total / scenes.length;
}

// ─── SceneStepAlignment (LLM 1회) ───

export const SCENE_STEP_ALIGNMENT_PROMPT = `당신은 요리 레시피의 품질 검수자입니다.
아래에 레시피의 각 단계(step)와 그 단계에 포함된 장면(scenes)이 있습니다.

## 평가 과제
각 장면(scene)의 label이 해당 단계의 description 텍스트 중 **어떤 문장에 대응하는지** 명확히 알 수 있는지 평가하세요.

## 판단 기준
- 장면의 label을 읽었을 때, 해당 step의 description 중 정확히 어떤 문장을 시각적으로 보여주는 것인지 바로 알 수 있어야 합니다.
- 예시 (좋음): step description "마늘을 편으로 썰어주세요" + scene label "마늘 편 써는 장면" → 바로 매칭됨
- 예시 (나쁨): step description "양념장을 만들어주세요" + scene label "조리 장면" → 어떤 동작인지 모호함

## 레시피 데이터
{{output}}

## 참고 (영상 원본 데이터)
{{expected}}`;

export const SCENE_STEP_ALIGNMENT_SCORES: ClassifierChoice = {
  A: 1.0,
  B: 0.7,
  C: 0.4,
  D: 0.1,
};
