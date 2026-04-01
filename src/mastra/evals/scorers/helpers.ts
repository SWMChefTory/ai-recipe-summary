import { readFileSync, existsSync } from "fs";
import { join } from "path";
import { google } from "@ai-sdk/google";
import { generateText } from "ai";
import type { GroundTruth } from "../collect-ground-truth";
import { extractVideoId } from "../../tools/analyze-video";

// ─── 타입 ───

export interface RecipeScene {
  label: string;
  start: string;
  end: string;
}

export interface RecipeStep {
  order: number;
  title: string;
  description: Array<{ content: string; start: string }>;
  tip?: string | string[] | null;
  knowledge?: string | null;
  scenes?: RecipeScene[] | null;
  timerSeconds?: number | null;
}

export interface ParsedRecipe {
  title?: string;
  description?: string;
  servings?: number;
  cookingTimeMinutes?: number;
  difficulty?: string;
  category?: string;
  ingredients?: Array<{
    name: string;
    amount?: { value: number | null; unit: string | null };
    substitute?: string;
  }>;
  tools?: Array<{ name: string }>;
  steps?: RecipeStep[];
  servingTip?: string | null;
  general_tips?: string[];
}

export interface GTEvent {
  time: string;
  endTime: string;
  type: string;
  visual: string;
  ingredients: string[] | null;
  tools: string[] | null;
}

// ─── 헬퍼 ───

export function timestampToSeconds(ts: string): number {
  const parts = ts.split(":").map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0];
}

// Braintrust 번들러가 __dirname을 바꾸므로, 프로젝트 루트에서 탐색
function resolveFixturesDir(): string {
  // 1. __dirname 기반 (로컬 실행)
  const candidates = [
    join(__dirname, "../fixtures"),
    join(__dirname, "../../evals/fixtures"),
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  // 2. cwd 기반 (번들러 환경)
  let dir = process.cwd();
  for (let i = 0; i < 10; i++) {
    const p = join(dir, "src/mastra/evals/fixtures");
    if (existsSync(p)) return p;
    const parent = join(dir, "..");
    if (parent === dir) break;
    dir = parent;
  }
  return join(process.cwd(), "src/mastra/evals/fixtures");
}

const FIXTURES_DIR = resolveFixturesDir();

export function loadGroundTruth(url: string): GroundTruth | null {
  const videoId = extractVideoId(url);
  if (!videoId) return null;
  const filePath = join(FIXTURES_DIR, `${videoId}.json`);
  if (!existsSync(filePath)) return null;
  return JSON.parse(readFileSync(filePath, "utf-8")) as GroundTruth;
}

export function getAllScenes(recipe: ParsedRecipe | null): RecipeScene[] {
  if (!recipe?.steps) return [];
  return recipe.steps
    .flatMap((s) => s.scenes ?? [])
    .filter((s): s is RecipeScene => s !== null && s.label !== undefined);
}

export function getCookingEvents(gt: GroundTruth | null): GTEvent[] {
  if (!gt?.visualAnalysis?.parsed) return [];
  return gt.visualAnalysis.parsed.filter((e) => e.type === "cooking");
}

// ─── Gemini LLM Classifier ───

export interface ClassifierChoice {
  [choice: string]: number;
}

export async function geminiClassifier(
  prompt: string,
  output: string,
  expected: string,
  choiceScores: ClassifierChoice,
  useCot = true
): Promise<{ score: number; metadata: { rationale?: string; choice?: string } }> {
  const choices = Object.keys(choiceScores);
  const choiceDesc = choices.map((c) => `${c} (${choiceScores[c]})`).join(", ");

  const fullPrompt = prompt
    .replace("{{output}}", output)
    .replace("{{expected}}", expected);

  const systemPrompt = useCot
    ? `아래 평가를 수행하세요. 먼저 간단히 reasoning을 한국어로 작성하고, 마지막 줄에 반드시 "Choice: X" 형식으로 선택지를 출력하세요.\n선택지: ${choiceDesc}`
    : `아래 평가를 수행하세요. "Choice: X" 형식으로만 답하세요.\n선택지: ${choiceDesc}`;

  const result = await generateText({
    model: google("gemini-2.5-flash"),
    system: systemPrompt,
    prompt: fullPrompt,
  });

  const text = result.text.trim();
  const choiceMatch = text.match(/Choice:\s*([A-Z])/i);
  const choice = choiceMatch?.[1]?.toUpperCase() ?? choices[choices.length - 1];
  const score = choiceScores[choice] ?? 0;
  const rationale = useCot ? text.replace(/Choice:\s*[A-Z].*/i, "").trim() : undefined;

  return { score, metadata: { rationale, choice } };
}

// ─── 재시도 래퍼 ───

export async function withRetry<T>(
  fn: () => T | Promise<T>,
  maxRetries = 3,
  baseDelay = 3000
): Promise<T> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (e: any) {
      if (e?.status === 429 && i < maxRetries - 1) {
        const delay = baseDelay * (i + 1);
        console.log(`  ⏳ Rate limit, ${delay}ms 대기 후 재시도 (${i + 1}/${maxRetries})`);
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
      throw e;
    }
  }
  throw new Error("withRetry: unreachable");
}
