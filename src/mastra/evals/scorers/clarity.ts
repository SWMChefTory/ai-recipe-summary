import { google } from "@ai-sdk/google";
import { generateText } from "ai";
import {
  type ParsedRecipe,
  type RecipeStep,
  type ClassifierChoice,
  timestampToSeconds,
  getCookingEvents,
  withRetry,
} from "./helpers";
import type { GroundTruth } from "../collect-ground-truth";

// ─── CookingActionCoverage (LLM 1회 per recipe) ───

const COOKING_ACTION_COVERAGE_PROMPT = `당신은 요리 레시피의 완성도를 평가하는 전문가입니다.

## 작업
아래에 두 가지 정보가 있습니다:
1. **레시피**: 각 단계(step)별 description
2. **영상 조리 동작**: step별 + 전체 영상의 모든 조리 동작

두 가지를 비교하여:
- 각 step 내에서 누락된 조리 동작
- 어떤 step에도 포함되지 않은 조리 동작
을 찾아주세요.

## 판단 기준
**"이 동작을 모르면 요리를 완성할 수 없는가?"가 핵심입니다.**

감점: 이 동작을 빠뜨리면 요리를 완성할 수 없거나 결과가 크게 달라지는 동작
감점하지 않음: 빠뜨려도 요리 완성에 영향이 없는 동작

## 점수 기준
각 step에 대해 0~100 점수를 매기고, 전체 레시피에 대해서도 "uncovered" 항목을 출력하세요:
- step 100: 영상의 모든 핵심 조리 동작이 description에 반영됨
- step 70: 대부분 반영되었지만 1~2개 소소한 동작 누락
- step 40: 핵심 조리 동작이 여러 개 누락
- step 0: 거의 반영 안 됨

## 출력
JSON으로만 출력하세요. 설명 없이.

{
  "steps": {
    "step1": { "score": 80, "missing": ["청양고추 씨 제거하기"] },
    "step2": { "score": 100, "missing": [] }
  },
  "uncovered": ["끓이는 중간에 저어주기", "뚜껑 덮기"]
}

- steps: 각 step 내에서 누락된 조리 동작
- uncovered: 영상에는 있지만 레시피의 어떤 step에도 없는 조리 동작 (요리에 필요한 것만)`;

export async function scoreCookingActionCoverage(
  recipe: ParsedRecipe | null,
  gt: GroundTruth | null
): Promise<{ score: number; stepScores: Record<string, number>; missing: string[]; details: string }> {
  if (!gt?.visualAnalysis?.parsed)
    return { score: 0, stepScores: {}, missing: [], details: "GT 없음" };
  if (!recipe?.steps || recipe.steps.length === 0)
    return { score: 0, stepScores: {}, missing: [], details: "레시피 steps 없음" };

  const cookingEvents = getCookingEvents(gt);
  if (cookingEvents.length === 0)
    return { score: 0, stepScores: {}, missing: [], details: "GT cooking 이벤트 없음" };

  // 영상 끝 시간 = GT의 마지막 이벤트 endTime
  const allEvents = gt.visualAnalysis.parsed;
  const videoEnd = allEvents.length > 0
    ? Math.max(...allEvents.map(e => timestampToSeconds(e.endTime)))
    : 9999;

  const stepTexts: string[] = [];

  for (let i = 0; i < recipe.steps.length; i++) {
    const step = recipe.steps[i];
    const nextStep = recipe.steps[i + 1];

    const descStarts = (step.description || [])
      .map(d => d.start)
      .filter(Boolean)
      .map(s => timestampToSeconds(s));
    if (descStarts.length === 0) continue;

    const stepStart = Math.min(...descStarts);
    const stepEnd = nextStep?.description?.[0]?.start
      ? timestampToSeconds(nextStep.description[0].start) - 1  // 다음 step start - 1초
      : videoEnd;  // 마지막 step은 영상 끝까지

    const stepGT = cookingEvents.filter(evt => {
      const evtStart = timestampToSeconds(evt.time);
      return evtStart >= stepStart && evtStart < stepEnd;
    });

    let text = `### step${step.order}: ${step.title}\n`;
    text += `레시피 description:\n`;
    for (const d of (step.description || [])) {
      text += `  - [${d.start}] ${d.content}\n`;
    }
    text += `영상에서 보이는 조리 동작:\n`;
    if (stepGT.length > 0) {
      const seen = new Set<string>();
      for (const evt of stepGT) {
        const key = evt.visual.slice(0, 40);
        if (!seen.has(key)) {
          seen.add(key);
          text += `  - [${evt.time}] ${evt.visual}\n`;
        }
      }
    } else {
      text += `  (이 시간대에 GT 조리 동작 없음)\n`;
    }

    stepTexts.push(text);
  }

  // 전체 GT 조리 동작 요약 (중복 제거)
  let allGTText = "\n\n## 영상의 전체 조리 동작 (시간순)\n";
  const seenAll = new Set<string>();
  for (const evt of cookingEvents) {
    const key = evt.visual.slice(0, 40);
    if (!seenAll.has(key)) {
      seenAll.add(key);
      allGTText += `- [${evt.time}] ${evt.visual}\n`;
    }
  }
  allGTText += "\n위 동작 중 레시피의 어떤 step에도 반영되지 않은 것이 있으면 uncovered에 넣어주세요.\n";

  const combined = stepTexts.join("\n") + allGTText;

  try {
    const result = await withRetry(async () => {
      const res = await generateText({
        model: google("gemini-2.5-flash"),
        system: COOKING_ACTION_COVERAGE_PROMPT,
        prompt: combined,
      });
      return res.text;
    });

    const cleaned = result.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
    const parsed = JSON.parse(cleaned) as {
      steps: Record<string, { score: number; missing: string[] }>;
      uncovered: string[];
    };

    const stepScores: Record<string, number> = {};
    const allMissing: string[] = [];

    // step별 missing
    for (const [key, val] of Object.entries(parsed.steps || {})) {
      stepScores[key] = val.score;
      if (val.missing?.length > 0) {
        allMissing.push(...val.missing.map(m => `${key}: ${m}`));
      }
    }

    // 어떤 step에도 없는 동작
    if (parsed.uncovered?.length > 0) {
      allMissing.push(...parsed.uncovered.map(m => `uncovered: ${m}`));
    }

    const values = Object.values(stepScores);
    const avg = values.length > 0
      ? values.reduce((a, b) => a + b, 0) / values.length / 100
      : 0;

    return { score: avg, stepScores, missing: allMissing, details: cleaned };
  } catch (e: any) {
    return { score: 0, stepScores: {}, missing: [], details: `LLM 실패: ${e.message?.slice(0, 100)}` };
  }
}

// ─── TextPlusSceneClarity (LLM 1회) ───

function getStepTimeRange(
  step: RecipeStep,
  nextStep: RecipeStep | null
): { start: number; end: number } | null {
  if (!step.description || step.description.length === 0) return null;
  const starts = step.description
    .map((d) => d.start)
    .filter(Boolean)
    .map((s) => timestampToSeconds(s));
  if (starts.length === 0) return null;

  const stepStart = Math.min(...starts);
  const stepEnd = nextStep?.description?.[0]?.start
    ? timestampToSeconds(nextStep.description[0].start)
    : Math.max(...starts) + 60;

  return { start: stepStart, end: stepEnd };
}

export function formatStepsForClarity(
  recipe: ParsedRecipe | null,
  gt: GroundTruth | null
): string {
  if (!recipe?.steps) return "레시피 없음";

  const cookingEvents = getCookingEvents(gt);

  return recipe.steps
    .map((step, idx) => {
      const nextStep = recipe.steps![idx + 1] ?? null;

      let text = `### ${step.order}단계: ${step.title}\n`;
      text += "조리 지시:\n";
      if (step.description) {
        for (const d of step.description) {
          text += `  - [${d.start}] ${d.content}\n`;
        }
      }

      if (step.scenes && step.scenes.length > 0) {
        text += "참고 장면:\n";
        for (const s of step.scenes) {
          text += `  🎬 "${s.label}" (${s.start}~${s.end})\n`;

          if (cookingEvents.length > 0) {
            const sceneStart = timestampToSeconds(s.start);
            const sceneEnd = timestampToSeconds(s.end);
            const matching = cookingEvents.filter((evt) => {
              const evtStart = timestampToSeconds(evt.time);
              const evtEnd = timestampToSeconds(evt.endTime);
              return evtStart >= sceneStart && evtEnd <= sceneEnd;
            });
            if (matching.length > 0) {
              text += `     실제 영상: ${matching.map((e) => e.visual).join(" → ")}\n`;
            }
          }
        }
      } else {
        text += "참고 장면: 없음\n";
      }

      if (step.tip) {
        const tips = Array.isArray(step.tip) ? step.tip : [step.tip];
        text += `팁: ${tips.join(" / ")}\n`;
      }

      if (cookingEvents.length > 0) {
        const range = getStepTimeRange(step, nextStep);
        if (range) {
          const stepEvents = cookingEvents.filter((evt) => {
            const evtStart = timestampToSeconds(evt.time);
            return evtStart >= range.start && evtStart < range.end;
          });
          if (stepEvents.length > 0) {
            text += `영상에서 이 시간대에 보이는 조리 동작:\n`;
            const seen = new Set<string>();
            for (const evt of stepEvents) {
              const key = evt.visual.slice(0, 30);
              if (!seen.has(key)) {
                seen.add(key);
                const ings = evt.ingredients ? ` (${evt.ingredients.join(", ")})` : "";
                text += `  [${evt.time}] ${evt.visual}${ings}\n`;
              }
            }
          }
        }
      }

      return text;
    })
    .join("\n");
}

export const TEXT_PLUS_SCENE_CLARITY_PROMPT = `당신은 요리를 많이 해보지 않은 20대 초보 요리사입니다.
계란 프라이, 라면 끓이기, 밥 짓기 같은 기본적인 요리는 할 수 있지만, 특수한 재료 손질이나 전문 조리 기법은 모릅니다.
아래 레시피를 단계별로 따라해야 합니다.

## 레시피 구조 설명
각 단계에는:
- **조리 지시**: 텍스트로 된 조리 방법
- **참고 장면**: 영상에서 해당 동작을 볼 수 있는 구간 (라벨 + 시간 + 실제 영상 내용)
- 장면이 "없음"이면 텍스트만으로 따라해야 함

## 중요한 전제
- 텍스트만으로 이해가 안 되는 건 **괜찮습니다**. (예: "편 썰기"가 뭔지 모르는 건 OK)
- 하지만 해당 단계에 장면이 제공되어 있다면, **"이 장면을 영상에서 찾아보면 되겠구나"라고 판단**할 수 있어야 합니다.
- 텍스트 + 장면 정보를 **함께** 봤는데도 "이걸 어떻게 하라는 거지?"라면 **실패**입니다.

## 평가 기준
1. **누락 체크**: 각 단계의 "영상에서 이 시간대에 보이는 조리 동작"과 "조리 지시"를 비교하세요. 영상에는 있는데 조리 지시에 빠진 중요한 동작이 있는가?
2. 텍스트로 이해 안 되는 부분에 장면이 잘 배치되어 있는가?
3. 장면 label이 "영상에서 이걸 찾아보면 되겠다"라고 느낄 만큼 구체적인가?
4. 장면의 "실제 영상" 내용이 조리 지시와 실제로 맞는가?
5. 장면이 없는 단계는 텍스트만으로도 충분히 따라할 수 있는가?
6. 전체적으로, 이 레시피를 보고 요리를 완성할 수 있겠는가?

## 레시피 (단계별)
{{output}}

## 참고: 영상 기본 정보
{{expected}}`;

export const TEXT_PLUS_SCENE_CLARITY_SCORES: ClassifierChoice = {
  A: 1.0,
  B: 0.7,
  C: 0.4,
  D: 0.1,
};
