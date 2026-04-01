import type { ParsedRecipe } from "./helpers";
import type { ExpectedIngredient } from "../dataset";

// ─── Completeness ───

export function scoreCompleteness(recipe: ParsedRecipe | null): number {
  if (!recipe) return 0;
  const required = [
    recipe.title,
    recipe.ingredients && recipe.ingredients.length > 0,
    recipe.steps && recipe.steps.length > 0,
    recipe.category,
    recipe.difficulty,
  ];
  const optional = [
    recipe.description,
    recipe.servings,
    recipe.cookingTimeMinutes,
  ];
  return (
    (required.filter(Boolean).length / required.length) * 0.7 +
    (optional.filter(Boolean).length / optional.length) * 0.3
  );
}

// ─── IngredientRecall ───

function normalizeName(name: string): string {
  return name.toLowerCase().replace(/\s/g, "");
}

type RecipeIngredient = NonNullable<ParsedRecipe["ingredients"]>[number];

export function findMatchingIngredient(
  recipeIngredients: ParsedRecipe["ingredients"],
  expectedName: string
): RecipeIngredient | null {
  const norm = normalizeName(expectedName);
  return (
    recipeIngredients?.find((i) => {
      const n = normalizeName(i.name);
      return n.includes(norm) || norm.includes(n);
    }) ?? null
  );
}

export function scoreIngredientRecall(
  recipe: ParsedRecipe | null,
  expectedIngredients: ExpectedIngredient[]
): { score: number; matched: string[]; missing: string[] } {
  if (!recipe?.ingredients || recipe.ingredients.length === 0)
    return { score: 0, matched: [], missing: expectedIngredients.map((e) => e.name) };
  if (expectedIngredients.length === 0)
    return { score: 1, matched: [], missing: [] };

  const matched: string[] = [];
  const missing: string[] = [];

  for (const expected of expectedIngredients) {
    const found = findMatchingIngredient(recipe.ingredients, expected.name);
    if (found) {
      matched.push(expected.name);
    } else {
      missing.push(expected.name);
    }
  }

  return {
    score: matched.length / expectedIngredients.length,
    matched,
    missing,
  };
}

// ─── AmountAccuracy ───

function getUnitGroup(unit: string): string | null {
  const u = unit.toLowerCase().trim();

  if (["큰술", "t", "tbsp", "스푼", "밥숟가락", "밥수저", "숟갈", "숟가락"].includes(u)) return "tablespoon";
  if (["작은술", "tsp", "티스푼", "커피수저"].includes(u)) return "teaspoon";
  if (["컵", "cup"].includes(u)) return "cup";
  if (["ml", "밀리리터", "cc"].includes(u)) return "ml";
  if (["l", "리터"].includes(u)) return "l";
  if (["g", "그램"].includes(u)) return "g";
  if (["kg", "킬로그램"].includes(u)) return "kg";
  if (["개", "알"].includes(u)) return "count";
  if (["대"].includes(u)) return "stalk";
  if (["장"].includes(u)) return "sheet";
  if (["모"].includes(u)) return "block";
  if (["봉지"].includes(u)) return "pack";
  if (["줄"].includes(u)) return "strip";
  if (["마리"].includes(u)) return "whole";
  if (["포기"].includes(u)) return "head";
  if (["쪽"].includes(u)) return "clove";

  return null;
}

export function scoreAmountAccuracy(
  recipe: ParsedRecipe | null,
  expectedIngredients: ExpectedIngredient[]
): { score: number; correct: string[]; wrong: string[]; details: string[] } {
  if (!recipe?.ingredients || recipe.ingredients.length === 0)
    return { score: 0, correct: [], wrong: [], details: [] };

  const withAmount = expectedIngredients.filter((e) => e.amount !== null);
  if (withAmount.length === 0)
    return { score: 1, correct: [], wrong: [], details: ["분량 기대값 없음"] };

  const correct: string[] = [];
  const wrong: string[] = [];
  const details: string[] = [];

  for (const expected of withAmount) {
    const found = findMatchingIngredient(recipe.ingredients, expected.name);
    if (!found || !found.amount) {
      wrong.push(expected.name);
      details.push(`${expected.name}: 재료 없거나 분량 없음`);
      continue;
    }

    const expAmt = expected.amount!;
    const gotAmt = found.amount;

    if (expAmt.value === null || gotAmt.value === null) {
      wrong.push(expected.name);
      details.push(`${expected.name}: value가 null`);
      continue;
    }

    const expGroup = getUnitGroup(expAmt.unit ?? "");
    const gotGroup = getUnitGroup(gotAmt.unit ?? "");
    const sameUnitSystem = expGroup !== null && gotGroup !== null && expGroup === gotGroup;

    if (!sameUnitSystem) {
      wrong.push(expected.name);
      details.push(
        `${expected.name}: 단위 체계 불일치 — 기대 ${expAmt.value}${expAmt.unit} → 실제 ${gotAmt.value}${gotAmt.unit}`
      );
      continue;
    }

    const valueMatch = Math.abs(gotAmt.value - expAmt.value) <= expAmt.value * 0.15;

    if (valueMatch) {
      correct.push(expected.name);
    } else {
      wrong.push(expected.name);
      details.push(
        `${expected.name}: 기대 ${expAmt.value}${expAmt.unit} → 실제 ${gotAmt.value}${gotAmt.unit}`
      );
    }
  }

  return {
    score: withAmount.length > 0 ? correct.length / withAmount.length : 1,
    correct,
    wrong,
    details,
  };
}

// ─── StepQuality ───

export function scoreStepQuality(recipe: ParsedRecipe | null): {
  score: number;
  issues: string[];
} {
  if (!recipe?.steps || recipe.steps.length === 0)
    return { score: 0, issues: ["steps 없음"] };

  let total = 0;
  let passed = 0;
  const issues: string[] = [];

  for (const step of recipe.steps) {
    total++;
    if (step.title?.length > 0) {
      passed++;
    } else {
      issues.push(`step${step.order}: title 없음`);
    }

    total++;
    if (step.description?.length >= 1 && step.description.length <= 4) {
      passed++;
    } else {
      issues.push(
        `step${step.order} "${step.title}": description ${step.description?.length ?? 0}개 (1~4 필요)`
      );
    }

    if (step.description) {
      for (const d of step.description) {
        total++;
        if (/[주하세]세요|십시오/.test(d.content)) {
          passed++;
        } else {
          issues.push(
            `step${step.order}: 지시문체 아님 — "${d.content.slice(0, 30)}…"`
          );
        }
      }
    }
  }

  total++;
  const orders = recipe.steps.map((s) => s.order);
  if (orders.every((v, i) => i === 0 || v >= orders[i - 1])) {
    passed++;
  } else {
    issues.push(`order 오름차순 아님: [${orders.join(",")}]`);
  }

  return { score: total > 0 ? passed / total : 0, issues };
}
