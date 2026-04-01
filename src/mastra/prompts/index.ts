/**
 * 프롬프트 관리 모듈
 *
 * 버전별 프롬프트를 관리합니다.
 * - v1: 5-phase 파이프라인 (phase1~5)
 * - v2: 단일 노드 (single)
 * - v3: 3-노드 워크플로우 (node1-extract, node2-ingredients, node3-refine)
 *
 * 환경변수 PROMPT_VERSION으로 버전 선택 (기본: v3)
 */

import { readFileSync, writeFileSync, existsSync } from "fs";
import { join } from "path";

function resolvePromptsDir(): string {
  if (process.env.PROJECT_ROOT) {
    return join(process.env.PROJECT_ROOT, "src/mastra/prompts");
  }

  let dir = process.cwd();
  for (let i = 0; i < 10; i++) {
    const promptsPath = join(dir, "src/mastra/prompts");
    if (existsSync(join(promptsPath, "v1")) || existsSync(join(promptsPath, "v2")) || existsSync(join(promptsPath, "v3"))) {
      return promptsPath;
    }
    const parent = join(dir, "..");
    if (parent === dir) break;
    dir = parent;
  }

  const candidates = [join(__dirname), join(__dirname, "../prompts")];
  for (const c of candidates) {
    if (existsSync(join(c, "v1")) || existsSync(join(c, "v2")) || existsSync(join(c, "v3"))) return c;
  }

  return join(process.cwd(), "src/mastra/prompts");
}

const PROMPTS_DIR = resolvePromptsDir();

export type PromptVersion = "v1" | "v2" | "v3";

export function getPromptVersion(): PromptVersion {
  return (process.env.PROMPT_VERSION as PromptVersion) || "v3";
}

const V1_FILES = {
  phase1: "phase1.md",
  phase2: "phase2.md",
  phase3: "phase3.md",
  phase4: "phase4.md",
  phase5: "phase5.md",
} as const;

const V2_FILES = {
  single: "single.md",
} as const;

const V3_FILES = {
  "node1-extract": "node1-extract.md",
  "node2-ingredients": "node2-ingredients.md",
  "node3-refine": "node3-refine.md",
  "node4-metadata": "node4-metadata.md",
  "node5-scene": "node5-scene.md",
} as const;

export type V1Phase = keyof typeof V1_FILES;
export type V2Phase = keyof typeof V2_FILES;
export type V3Phase = keyof typeof V3_FILES;
export type PromptPhase = V1Phase | V2Phase | V3Phase;

export function loadPrompt(phase: PromptPhase, version?: PromptVersion): string {
  const ver = version ?? getPromptVersion();

  const fileMap: Record<string, Record<string, string>> = {
    v1: V1_FILES,
    v2: V2_FILES,
    v3: V3_FILES,
  };

  // 지정된 버전에서 찾기
  if (fileMap[ver] && phase in fileMap[ver]) {
    const filePath = join(PROMPTS_DIR, ver, fileMap[ver][phase]);
    return readFileSync(filePath, "utf-8");
  }

  // fallback: 다른 버전에서 찾기
  for (const [v, files] of Object.entries(fileMap)) {
    if (phase in files) {
      const filePath = join(PROMPTS_DIR, v, files[phase]);
      if (existsSync(filePath)) return readFileSync(filePath, "utf-8");
    }
  }

  throw new Error(`Prompt not found: ${phase} (version: ${ver})`);
}

export function savePrompt(phase: PromptPhase, content: string, version?: PromptVersion): void {
  const ver = version ?? getPromptVersion();

  const fileMap: Record<string, Record<string, string>> = {
    v1: V1_FILES,
    v2: V2_FILES,
    v3: V3_FILES,
  };

  if (fileMap[ver] && phase in fileMap[ver]) {
    const filePath = join(PROMPTS_DIR, ver, fileMap[ver][phase]);
    writeFileSync(filePath, content, "utf-8");
    return;
  }

  throw new Error(`Cannot save prompt: ${phase} (version: ${ver})`);
}
