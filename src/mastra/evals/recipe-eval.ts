/**
 * Braintrust 레시피 품질 평가
 *
 * 실행: npx braintrust eval src/mastra/evals/recipe-eval.ts
 *
 * ── 평가 항목 (11개) ──
 *
 * [구조 검증]
 * 1. Completeness          — 필수 필드 존재 여부
 * 2. IngredientRecall      — 기대 재료를 빠짐없이 추출했는가
 * 3. AmountAccuracy        — 분량 value/unit 정확도
 * 4. StepQuality           — 지시문체, description 개수, 시간순
 *
 * [장면 품질 — GT 기반]
 * 5. SceneTimestampAccuracy — 장면 시간이 GT와 일치하는가 (LLM)
 * 6. CookingActionCoverage  — GT 조리 동작이 레시피에 반영되었는가 (LLM)
 * 7. SceneCoverage          — 장면 배치가 적절한가 (LLM)
 * 8. SceneLabelConciseness  — 라벨이 3~8자로 간결한가
 * 9. SceneStepAlignment     — 장면이 step 텍스트와 매칭되는가 (LLM)
 *
 * [최종 품질]
 * 10. TextPlusSceneClarity  — 텍스트+장면으로 초보자가 이해 가능한가 (LLM)
 *
 * [뷰포트]
 * 11. StepViewportFit       — iPhone Mini 한 화면에 들어오는가 (Playwright)
 */

import { Eval } from "braintrust";
import { readFileSync, existsSync, writeFileSync } from "fs";
import { join } from "path";
import { execFileSync } from "child_process";
import { evalDataset, type EvalCase } from "./dataset";
import { analyzeYouTubeVideo, extractVideoId } from "../tools/analyze-video";

// ─── Scorers ───
import {
  type ParsedRecipe,
  loadGroundTruth,
  getAllScenes,
  getCookingEvents,
  geminiClassifier,
  withRetry,
} from "./scorers/helpers";
import {
  scoreCompleteness,
  scoreIngredientRecall,
  scoreAmountAccuracy,
  scoreStepQuality,
} from "./scorers/structure";
import {
  scoreSceneTimestampAccuracy,
  SCENE_COVERAGE_PROMPT,
  SCENE_COVERAGE_SCORES,
  scoreSceneLabelConciseness,
  SCENE_STEP_ALIGNMENT_PROMPT,
  SCENE_STEP_ALIGNMENT_SCORES,
} from "./scorers/scene";
import {
  scoreCookingActionCoverage,
  formatStepsForClarity,
  TEXT_PLUS_SCENE_CLARITY_PROMPT,
  TEXT_PLUS_SCENE_CLARITY_SCORES,
} from "./scorers/clarity";

// ─── 레시피 생성 (캐시 지원) ───

const RECIPES_DIR = join(__dirname, "fixtures", "recipes");

async function generateRecipe(url: string): Promise<{
  raw: string;
  parsed: ParsedRecipe | null;
  cached: boolean;
}> {
  const videoId = extractVideoId(url);
  const cachePath = videoId ? join(RECIPES_DIR, `${videoId}.json`) : null;

  if (cachePath && existsSync(cachePath) && !process.env.FORCE_REGENERATE) {
    const cached = JSON.parse(readFileSync(cachePath, "utf-8")) as {
      raw: string;
      generatedAt: string;
    };
    try {
      return { raw: cached.raw, parsed: JSON.parse(cached.raw) as ParsedRecipe, cached: true };
    } catch {
      return { raw: cached.raw, parsed: null, cached: true };
    }
  }

  const result = await analyzeYouTubeVideo.execute!({ url }, {} as any);
  const raw = (result as { recipe: string }).recipe;

  if (cachePath) {
    const cacheData = { raw, videoId, generatedAt: new Date().toISOString() };
    writeFileSync(cachePath, JSON.stringify(cacheData, null, 2), "utf-8");
  }

  try {
    return { raw, parsed: JSON.parse(raw) as ParsedRecipe, cached: false };
  } catch {
    return { raw, parsed: null, cached: false };
  }
}

// ─── Braintrust Eval ───

Eval("recipe-create", {
  experimentName: "recipe-quality-eval-v2",
  timeout: 600000, // 10분

  data: () =>
    evalDataset.slice(0, 10).map((testCase) => ({
      input: { url: testCase.url, name: testCase.name },
      expected: testCase.expectedCriteria,
      metadata: { name: testCase.name },
    })),

  task: async (input: { url: string; name: string }) => {
    console.log(`\n🍳 [${input.name}] 레시피 생성 중...`);
    const { raw, parsed, cached } = await generateRecipe(input.url);
    console.log(
      `✅ [${input.name}] ${cached ? "(캐시)" : "(새로 생성)"} — ${parsed?.steps?.length ?? 0}단계, ${getAllScenes(parsed).length}장면`
    );
    return { raw, parsed };
  },

  scores: [
    // ── 구조 검증 ──

    async ({ output }) => ({
      name: "Completeness",
      score: scoreCompleteness(
        (output as { parsed: ParsedRecipe | null }).parsed
      ),
    }),

    async ({ output, expected }) => {
      const { parsed } = output as { parsed: ParsedRecipe | null };
      const criteria = expected as EvalCase["expectedCriteria"];
      const result = scoreIngredientRecall(parsed, criteria.expectedIngredients);
      return {
        name: "IngredientRecall",
        score: result.score,
        metadata: {
          ingredients: parsed?.ingredients?.map((i) => i.name) ?? [],
          matched: result.matched,
          missing: result.missing,
          total: criteria.expectedIngredients.length,
        },
      };
    },

    async ({ output, expected }) => {
      const { parsed } = output as { parsed: ParsedRecipe | null };
      const criteria = expected as EvalCase["expectedCriteria"];
      const result = scoreAmountAccuracy(parsed, criteria.expectedIngredients);
      return {
        name: "AmountAccuracy",
        score: result.score,
        metadata: {
          correct: result.correct,
          wrong: result.wrong,
          details: result.details,
        },
      };
    },

    async ({ output }) => {
      const result = scoreStepQuality(
        (output as { parsed: ParsedRecipe | null }).parsed
      );
      return {
        name: "StepQuality",
        score: result.score,
        metadata: { issues: result.issues },
      };
    },

    // ── 장면 품질 (GT 기반) ──

    async ({ output, input }) => {
      const { parsed } = output as { parsed: ParsedRecipe | null };
      const gt = loadGroundTruth((input as { url: string }).url);
      const result = await scoreSceneTimestampAccuracy(parsed, gt);
      return {
        name: "SceneTimestampAccuracy",
        score: result.score,
        metadata: {
          totalScenes: getAllScenes(parsed).length,
          gtCookingEvents: getCookingEvents(gt).length,
          details: result.details,
        },
      };
    },

    async ({ output, input }) => {
      const { parsed } = output as { parsed: ParsedRecipe | null };
      const gt = loadGroundTruth((input as { url: string }).url);
      const result = await scoreCookingActionCoverage(parsed, gt);
      return {
        name: "CookingActionCoverage",
        score: result.score,
        metadata: {
          stepScores: result.stepScores,
          missing: result.missing,
          details: result.details,
        },
      };
    },

    async ({ output, input }) => {
      const { raw } = output as { raw: string };
      const gt = loadGroundTruth((input as { url: string }).url);
      const gtSummary = gt
        ? JSON.stringify(
            { videoInfo: gt.videoInfo, cookingEvents: getCookingEvents(gt).slice(0, 30) },
            null, 2
          )
        : "Ground Truth 없음";
      const result = await withRetry(() =>
        geminiClassifier(SCENE_COVERAGE_PROMPT, raw, gtSummary, SCENE_COVERAGE_SCORES)
      );
      return {
        name: "SceneCoverage",
        score: result.score ?? 0,
        metadata: { rationale: result.metadata?.rationale, choice: result.metadata?.choice },
      };
    },

    async ({ output }) => ({
      name: "SceneLabelConciseness",
      score: scoreSceneLabelConciseness(
        (output as { parsed: ParsedRecipe | null }).parsed
      ),
      metadata: {
        labels: getAllScenes(
          (output as { parsed: ParsedRecipe | null }).parsed
        ).map((s) => `${s.label} (${s.label.length}자)`),
      },
    }),

    // ── LLM Judge ──

    async ({ output, input }) => {
      const { raw } = output as { raw: string };
      const gt = loadGroundTruth((input as { url: string }).url);
      const gtSummary = gt
        ? JSON.stringify(
            { videoInfo: gt.videoInfo, cookingEvents: getCookingEvents(gt).slice(0, 30) },
            null, 2
          )
        : "Ground Truth 없음";
      const result = await withRetry(() =>
        geminiClassifier(SCENE_STEP_ALIGNMENT_PROMPT, raw, gtSummary, SCENE_STEP_ALIGNMENT_SCORES)
      );
      return {
        name: "SceneStepAlignment",
        score: result.score ?? 0,
        metadata: { rationale: result.metadata?.rationale, choice: result.metadata?.choice },
      };
    },

    // ── 뷰포트 (Playwright) ──

    async ({ output }) => {
      const { parsed } = output as { parsed: ParsedRecipe | null };
      if (!parsed?.steps || parsed.steps.length === 0) {
        return { name: "StepViewportFit", score: 0 };
      }
      try {
        const stepsJson = JSON.stringify(parsed.steps);
        const stdout = execFileSync(
          "npx",
          ["tsx", join(__dirname, "run-viewport-check.ts")],
          { input: stepsJson, encoding: "utf-8", timeout: 30000 }
        );
        const result = JSON.parse(stdout) as {
          score: number;
          details: Array<{
            stepOrder: number;
            stepTitle: string;
            contentHeight: number;
            availableHeight: number;
            fits: boolean;
            overflowPx: number;
          }>;
        };
        const overflowSteps = result.details
          .filter((d) => !d.fits)
          .map((d) => `step${d.stepOrder} "${d.stepTitle}" +${d.overflowPx}px`);
        return {
          name: "StepViewportFit",
          score: result.score,
          metadata: {
            fitsCount: result.details.filter((d) => d.fits).length,
            totalSteps: result.details.length,
            availableHeight: result.details[0]?.availableHeight,
            overflowSteps,
          },
        };
      } catch (e: any) {
        return {
          name: "StepViewportFit",
          score: 0,
          metadata: { error: e.message?.slice(0, 200) },
        };
      }
    },
  ],
});
