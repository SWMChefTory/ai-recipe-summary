/**
 * StepViewportFit 스코어러
 *
 * 각 recipe step을 실제 앱(native-step/[id].tsx)과 동일한 CSS로 렌더링한 뒤
 * iPhone Mini 뷰포트(375×812)에서 스크롤 없이 한 화면에 들어오는지 체크합니다.
 *
 * 사용: Playwright로 HTML을 렌더링하고 scrollHeight vs viewportHeight 비교
 */

import { chromium, type Browser } from "playwright";

// iPhone Mini (iPhone 13 mini) 기준
const IPHONE_MINI = {
  width: 375,
  height: 812,
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
};

// 고정 영역 높이 계산 (native-step/[id].tsx 기준)
const FIXED_HEIGHTS = {
  statusBar: 47, // iOS 상태바 (safe area top)
  header: 44, // 헤더 높이
  progressBar: 10, // 진행바 (4 height + 6 paddingBottom)
  video: 211, // 16:9 비율 (375 / 16 * 9 ≈ 211)
  bottomBar: 82, // 그래디언트(48) + 네비(34) + safe area bottom
};

const CONTENT_AREA_HEIGHT =
  IPHONE_MINI.height -
  FIXED_HEIGHTS.statusBar -
  FIXED_HEIGHTS.header -
  FIXED_HEIGHTS.progressBar -
  FIXED_HEIGHTS.video -
  FIXED_HEIGHTS.bottomBar;
// ≈ 418px 사용 가능

interface RecipeStep {
  order: number;
  title: string;
  description: Array<{ content: string; start?: string }>;
  scenes?: Array<{ label: string; start: string; end: string }> | null;
  tip?: string | string[] | null;
}

/**
 * Step 1개를 native-step 페이지와 동일한 CSS로 렌더링하는 HTML 생성
 * 비디오/헤더/하단바 제외 — 스크롤 영역(콘텐츠) 부분만 측정
 */
function buildStepHTML(step: RecipeStep): string {
  const descriptions = Array.isArray(step.description)
    ? step.description
    : [step.description];

  const descHTML = descriptions
    .map(
      (d) => `
    <div class="desc-row">
      <span class="desc-dot">·</span>
      <span class="desc-text">${typeof d === "string" ? d : d.content}</span>
    </div>`
    )
    .join("");

  const scenes = step.scenes ?? [];
  const sceneHTML = scenes
    .map(
      (s, i) => `
    <div class="scene-chip${i === 0 ? " scene-chip-active" : ""}">
      <span class="scene-chip-text${i === 0 ? " scene-chip-text-active" : ""}">${i + 1}. ${s.label}</span>
    </div>`
    )
    .join("");

  return `<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=${IPHONE_MINI.width}, initial-scale=1">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #000;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
  }

  /* 콘텐츠 영역 — contentInner 스타일 그대로 */
  .content-inner {
    padding: 14px 20px 0 20px;
  }

  /* step 제목 */
  .step-title {
    color: #fff;
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 12px;
  }

  /* 설명 리스트 */
  .desc-list { display: flex; flex-direction: column; gap: 8px; }
  .desc-row { display: flex; align-items: flex-start; }
  .desc-dot {
    color: #f97316;
    font-size: 20px;
    font-weight: 700;
    margin-right: 8px;
    flex-shrink: 0;
  }
  .desc-text {
    flex: 1;
    color: rgba(255,255,255,0.95);
    font-size: 18px;
    line-height: 26px;
  }

  /* 장면 칩 */
  .scenes-wrap { margin-top: 14px; }
  .scenes-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .scene-chip {
    padding: 8px 14px;
    border-radius: 20px;
    border: 1px solid rgba(255,255,255,0.12);
    background: rgba(255,255,255,0.06);
  }
  .scene-chip-active {
    background: rgba(249,115,22,0.2);
    border-color: rgba(251,146,60,0.5);
  }
  .scene-chip-text {
    font-size: 13px;
    font-weight: 500;
    color: rgba(255,255,255,0.8);
    white-space: nowrap;
  }
  .scene-chip-text-active { color: rgb(253,186,116); }
</style>
</head>
<body>
  <div class="content-inner" id="content">
    <div class="step-title">${step.title}</div>
    <div class="desc-list">${descHTML}</div>
    ${
      scenes.length > 0
        ? `<div class="scenes-wrap"><div class="scenes-row">${sceneHTML}</div></div>`
        : ""
    }
  </div>
</body>
</html>`;
}

export interface ViewportCheckResult {
  /** 전체 step 중 한 화면에 들어오는 비율 (0~1) */
  score: number;
  /** 각 step별 상세 결과 */
  details: Array<{
    stepOrder: number;
    stepTitle: string;
    contentHeight: number;
    availableHeight: number;
    fits: boolean;
    overflowPx: number;
  }>;
}

/**
 * 모든 step을 iPhone Mini 뷰포트에서 체크
 */
export async function checkStepViewportFit(
  steps: RecipeStep[]
): Promise<ViewportCheckResult> {
  let browser: Browser | null = null;

  try {
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: {
        width: IPHONE_MINI.width,
        height: IPHONE_MINI.height,
      },
      deviceScaleFactor: IPHONE_MINI.deviceScaleFactor,
      isMobile: IPHONE_MINI.isMobile,
      hasTouch: IPHONE_MINI.hasTouch,
    });

    const details: ViewportCheckResult["details"] = [];

    for (const step of steps) {
      const page = await context.newPage();
      const html = buildStepHTML(step);
      await page.setContent(html, { waitUntil: "load" });

      // 콘텐츠 영역 높이 측정
      const contentHeight = await page.evaluate(() => {
        const el = document.getElementById("content");
        return el ? el.scrollHeight : 0;
      });

      const fits = contentHeight <= CONTENT_AREA_HEIGHT;
      const overflowPx = fits ? 0 : contentHeight - CONTENT_AREA_HEIGHT;

      details.push({
        stepOrder: step.order,
        stepTitle: step.title,
        contentHeight,
        availableHeight: CONTENT_AREA_HEIGHT,
        fits,
        overflowPx,
      });

      await page.close();
    }

    const fitsCount = details.filter((d) => d.fits).length;
    const score = steps.length > 0 ? fitsCount / steps.length : 0;

    return { score, details };
  } finally {
    if (browser) await browser.close();
  }
}
