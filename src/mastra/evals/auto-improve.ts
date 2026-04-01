/**
 * 자동 프롬프트 개선 루프
 *
 * 실행: npx tsx src/mastra/evals/auto-improve.ts
 *
 * 흐름:
 * 1. eval 실행 → Braintrust 결과에서 낮은 점수 스코어러 추출
 * 2. 해당 스코어러와 관련된 Phase 프롬프트 + 실패 케이스를 LLM에게 전달
 * 3. LLM이 프롬프트 개선안 생성
 * 4. 개선된 프롬프트 저장 → 재eval → 점수 비교
 * 5. 개선되면 유지, 퇴보하면 롤백
 */

import "dotenv/config";
import { readFileSync, writeFileSync, copyFileSync, existsSync } from "fs";
import { join } from "path";
import { execSync } from "child_process";
import { google } from "@ai-sdk/google";
import { generateText } from "ai";
import {
  loadPrompt,
  savePrompt,
  getPromptVersion,
  type PromptPhase,
} from "../prompts";

const ROOT = join(__dirname, "../../..");
const PROMPTS_DIR = join(__dirname, "../prompts");
const BACKUP_DIR = join(PROMPTS_DIR, ".backup");

// ─── 스코어러 → Phase 매핑 ───

// v1: 스코어러 → Phase 매핑 (5-phase)
const V1_SCORER_TO_PHASES: Record<string, PromptPhase[]> = {
  SceneTimestampAccuracy: ["phase1", "phase5"],
  SceneLabelConciseness: ["phase5"],
  SceneCoverage: ["phase4", "phase5"],
  SceneStepAlignment: ["phase5"],
  TextPlusSceneClarity: ["phase2", "phase4", "phase5"],
  StepQuality: ["phase2", "phase3"],
  Completeness: ["phase2"],
  IngredientRecall: ["phase1", "phase2"],
  AmountAccuracy: ["phase2"],
  StepViewportFit: ["phase2", "phase5"],
  TimestampOverlap: ["phase1"],
  SceneTransitionAccuracy: ["phase1"],
  EventCoverage: ["phase1"],
  VisualDetailMatch: ["phase1"],
  HallucinationCheck: ["phase1"],
};

// v2: 모든 스코어러가 single 프롬프트 하나에 매핑
const V2_SCORER_TO_PHASES: Record<string, PromptPhase[]> = {
  SceneTimestampAccuracy: ["single"],
  SceneLabelConciseness: ["single"],
  SceneCoverage: ["single"],
  SceneStepAlignment: ["single"],
  TextPlusSceneClarity: ["single"],
  StepQuality: ["single"],
  Completeness: ["single"],
  IngredientRecall: ["single"],
  AmountAccuracy: ["single"],
  StepViewportFit: ["single"],
};

function getScorerToPhases(): Record<string, PromptPhase[]> {
  return getPromptVersion() === "v1" ? V1_SCORER_TO_PHASES : V2_SCORER_TO_PHASES;
}

// ─── eval 실행 & 결과 파싱 ───

interface EvalResult {
  scores: Record<string, number>;
  raw: string;
}

function runEval(): EvalResult {
  const evalCmd = process.env.EVAL_CMD || "npm run eval:phase1";
  console.log(`\n📊 ${evalCmd} 실행 중...\n`);
  const raw = execSync(`${evalCmd} 2>&1`, {
    cwd: ROOT,
    encoding: "utf-8",
    timeout: 600_000,
  });

  // Experiment summary에서 점수 추출
  const scores: Record<string, number> = {};
  const scoreRegex = /◯\s+(\S+)\s+([\d.]+)%/g;
  let match;
  while ((match = scoreRegex.exec(raw)) !== null) {
    // Braintrust가 긴 이름을 "…"으로 자르므로 원래 이름으로 복원
    const name = resolveScoreName(match[1]);
    scores[name] = parseFloat(match[2]);
  }

  return { scores, raw };
}

/** 잘린 스코어러 이름을 원래 이름으로 복원 */
function resolveScoreName(truncated: string): string {
  const cleaned = truncated.replace(/…$/, "");
  const allNames = Object.keys(getScorerToPhases());
  // 정확히 일치하면 그대로
  if (allNames.includes(cleaned)) return cleaned;
  // 잘린 이름으로 시작하는 것 찾기
  const found = allNames.find((n) => n.startsWith(cleaned));
  return found || truncated;
}

// ─── 프롬프트 백업 & 롤백 ───

function getPhases(): PromptPhase[] {
  const ver = getPromptVersion();
  if (ver === "v1") return ["phase1", "phase2", "phase3", "phase4", "phase5"];
  return ["single"];
}

function backupPrompts(): void {
  if (!existsSync(BACKUP_DIR)) {
    execSync(`mkdir -p "${BACKUP_DIR}"`);
  }
  const ver = getPromptVersion();
  for (const phase of getPhases()) {
    const src = join(PROMPTS_DIR, ver, `${phase}.txt`);
    const dst = join(BACKUP_DIR, `${phase}.txt`);
    if (existsSync(src)) copyFileSync(src, dst);
  }
  console.log("💾 프롬프트 백업 완료");
}

function rollbackPrompts(): void {
  const ver = getPromptVersion();
  for (const phase of getPhases()) {
    const src = join(BACKUP_DIR, `${phase}.txt`);
    const dst = join(PROMPTS_DIR, ver, `${phase}.txt`);
    if (existsSync(src)) copyFileSync(src, dst);
  }
  console.log("⏪ 프롬프트 롤백 완료");
}

// ─── LLM에게 프롬프트 개선 요청 ───

async function improvePrompt(
  phase: PromptPhase,
  currentPrompt: string,
  scorerName: string,
  currentScore: number,
  scorerDescription: string
): Promise<string> {
  const systemPrompt = `당신은 LLM 프롬프트 엔지니어링 전문가입니다.
아래 프롬프트는 YouTube 요리 영상에서 레시피를 추출하는 AI 파이프라인의 일부입니다.

## 현재 문제
"${scorerName}" 평가 항목에서 ${currentScore}% 점수가 나왔습니다.

## 평가 기준 설명
${scorerDescription}

## 규칙
1. 프롬프트의 핵심 목적과 기존 규칙은 유지하세요.
2. 문제가 되는 평가 항목의 점수를 올리기 위한 **구체적인 규칙/지시만 추가**하세요.
3. 기존 내용을 삭제하지 마세요. 추가하거나 강화만 하세요.
4. 출력은 **수정된 전체 프롬프트 텍스트만** 반환하세요. 설명이나 마크다운 없이.`;

  const result = await generateText({
    model: google("gemini-3.1-pro-preview"),
    system: systemPrompt,
    prompt: `## 현재 프롬프트 (${phase})
${currentPrompt}

## 요청
위 프롬프트를 수정하여 "${scorerName}" 점수를 ${currentScore}%에서 개선하세요.
수정된 전체 프롬프트 텍스트만 반환하세요.`,
  });

  return result.text.trim();
}

// ─── 스코어러별 설명 ───

const SCORER_DESCRIPTIONS: Record<string, string> = {
  SceneTimestampAccuracy:
    "추출된 장면(scene)의 start~end 구간이 영상의 실제 조리 동작과 시간/내용 모두 일치하는지. GT cooking 이벤트의 visual/ingredients 텍스트와 scene label의 키워드가 매칭되어야 함.",
  SceneLabelConciseness:
    '장면 라벨이 12자 이내로 짧고 잘 요약되어야 함. 사용자가 소리내어 따라 부르는 용도. 3~8자가 이상적, 12자 초과 시 감점. 예: "마늘 편썰기", "소스 농도"',
  SceneCoverage:
    "텍스트만으로 이해 어려운 동작에만 장면이 있어야 함. 불필요한 곳에 있으면 과도, 필요한 곳에 없으면 부족. 단순 투입/수치 명확한 지시에는 장면 불필요.",
  SceneStepAlignment:
    "장면 label을 읽었을 때 해당 step의 description 중 정확히 어떤 문장에 대응하는지 바로 알 수 있어야 함.",
  TextPlusSceneClarity:
    "텍스트만으로 이해 안 되는 건 OK. 하지만 텍스트+장면까지 봤는데도 이해 못하면 실패. 장면이 필요한 곳에 잘 배치되어야 함.",
  StepQuality:
    "지시문체(~주세요) 사용, description 1~4개 이내, 시간순 정렬.",
  Completeness:
    "필수 필드(title, ingredients, steps, category, difficulty) 존재 여부.",
  IngredientRecall:
    "영상에서 확인된 전체 재료 목록 대비 추출된 재료의 recall. 빠진 재료가 없어야 함.",
  AmountAccuracy:
    "영상에서 분량이 언급된 재료의 value/unit이 정확한가. ±10% 허용, 단위 정규화 후 비교.",
  StepViewportFit:
    "iPhone Mini(375×812) 한 화면에 step 콘텐츠가 스크롤 없이 들어오는지. 콘텐츠 가용 높이 418px.",
};

// ─── 메인 루프 ───

async function main() {
  const MAX_ITERATIONS = Number(process.env.MAX_ITERATIONS) || 3;
  const SCORE_THRESHOLD = Number(process.env.SCORE_THRESHOLD) || 70;

  console.log("🔄 자동 프롬프트 개선 루프 시작");
  console.log(`   최대 반복: ${MAX_ITERATIONS}회`);
  console.log(`   목표 점수: 모든 스코어러 ${SCORE_THRESHOLD}% 이상\n`);

  // 초기 eval
  let evalResult = runEval();
  console.log("\n📈 초기 점수:");
  for (const [name, score] of Object.entries(evalResult.scores)) {
    const flag = score < SCORE_THRESHOLD ? " ⚠️" : " ✅";
    console.log(`   ${name}: ${score}%${flag}`);
  }

  for (let iter = 1; iter <= MAX_ITERATIONS; iter++) {
    // 목표 미달 스코어러 찾기
    const lowScorers = Object.entries(evalResult.scores)
      .filter(([, score]) => score < SCORE_THRESHOLD)
      .sort((a, b) => a[1] - b[1]); // 점수 낮은 순

    if (lowScorers.length === 0) {
      console.log(`\n🎉 모든 스코어러가 ${SCORE_THRESHOLD}% 이상! 완료.`);
      break;
    }

    console.log(`\n═══ 반복 ${iter}/${MAX_ITERATIONS} ═══`);
    console.log(`개선 필요: ${lowScorers.map(([n, s]) => `${n}(${s}%)`).join(", ")}`);

    // 가장 점수 낮은 스코어러부터 개선
    const [targetScorer, targetScore] = lowScorers[0];
    const targetPhases = getScorerToPhases()[targetScorer];

    if (!targetPhases) {
      console.log(`⏭️  ${targetScorer}에 매핑된 Phase가 없음 — 스킵`);
      continue;
    }

    console.log(`\n🎯 타겟: ${targetScorer} (${targetScore}%) → Phase: ${targetPhases.join(", ")}`);

    // 백업
    backupPrompts();

    // 각 관련 Phase 프롬프트 개선
    let improved = false;
    for (const phase of targetPhases) {
      const currentPrompt = loadPrompt(phase);
      console.log(`\n🔧 ${phase} 프롬프트 개선 중...`);

      try {
        const newPrompt = await improvePrompt(
          phase,
          currentPrompt,
          targetScorer,
          targetScore,
          SCORER_DESCRIPTIONS[targetScorer] || targetScorer
        );

        // 변경이 있는지 확인
        if (newPrompt === currentPrompt) {
          console.log(`   변경 없음 — 스킵`);
          continue;
        }

        // 새 프롬프트 저장
        savePrompt(phase, newPrompt);
        console.log(`   ✅ ${phase} 프롬프트 업데이트 (${currentPrompt.length}자 → ${newPrompt.length}자)`);
        improved = true;
      } catch (e: any) {
        console.log(`   ❌ ${phase} 개선 실패: ${e.message?.slice(0, 100)}`);
      }
    }

    if (!improved) {
      console.log("변경된 프롬프트 없음 — 다음 스코어러로");
      continue;
    }

    // 재eval
    const newResult = runEval();
    const newScore = newResult.scores[targetScorer] ?? 0;
    const oldScore = targetScore;
    const diff = newScore - oldScore;

    console.log(`\n📊 ${targetScorer}: ${oldScore}% → ${newScore}% (${diff >= 0 ? "+" : ""}${diff.toFixed(1)}%)`);

    // 전체 점수 비교
    let totalImproved = 0;
    let totalRegressed = 0;
    for (const [name, newS] of Object.entries(newResult.scores)) {
      const oldS = evalResult.scores[name] ?? 0;
      const d = newS - oldS;
      if (d > 1) totalImproved++;
      if (d < -1) totalRegressed++;
      if (Math.abs(d) > 0.5) {
        const arrow = d > 0 ? "📈" : "📉";
        console.log(`   ${arrow} ${name}: ${oldS}% → ${newS}% (${d >= 0 ? "+" : ""}${d.toFixed(1)}%)`);
      }
    }

    // 판정: 타겟 개선 + 전체 퇴보 없으면 유지
    if (diff > 0 && totalRegressed === 0) {
      console.log(`\n✅ 개선 확인 — 프롬프트 유지`);
      evalResult = newResult;
    } else if (diff > 0 && totalRegressed > 0) {
      console.log(`\n⚠️ 타겟은 개선됐지만 ${totalRegressed}개 퇴보 — 프롬프트 유지 (주의)`);
      evalResult = newResult;
    } else {
      console.log(`\n❌ 개선 없음 또는 퇴보 — 롤백`);
      rollbackPrompts();
    }
  }

  // 최종 결과
  console.log("\n═══ 최종 점수 ═══");
  for (const [name, score] of Object.entries(evalResult.scores).sort((a, b) => a[1] - b[1])) {
    const flag = score < SCORE_THRESHOLD ? " ⚠️" : " ✅";
    console.log(`   ${name}: ${score}%${flag}`);
  }
}

main().catch(console.error);
