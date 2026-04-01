/**
 * 레시피 평가용 테스트 데이터셋 — 30개 큐레이션
 *
 * 선정 기준:
 * - 채널(크리에이터) 중복 없음 — 최대한 다양한 사람
 * - 카테고리 다양성 (국/찌개, 볶음/구이, 밥/면, 분식, 반찬, 중식, 양식, 디저트)
 * - 인기 영상 위주
 *
 * expectedIngredients는 GT fixture의 더보기란 + 시각분석(화면 텍스트) + 자막을 교차검증하여 작성.
 * amount: 영상(더보기란/자막/화면 텍스트) 어디에서든 분량이 확인된 경우 기입, 없으면 null.
 */

/** 기대 재료 — 영상에서 확인된 분량이 있으면 amount, 없으면 null */
export interface ExpectedIngredient {
  name: string;
  amount: { value: number; unit: string } | null;
}

export interface EvalCase {
  /** 테스트 케이스 이름 */
  name: string;
  /** YouTube 영상 URL */
  url: string;
  /** 기대하는 레시피 품질 기준 */
  expectedCriteria: {
    /** 예상 요리 이름 키워드 */
    titleKeywords: string[];
    /** 최소 단계 수 */
    minSteps: number;
    /** 영상에서 확인된 전체 재료 목록 (분량 포함) */
    expectedIngredients: ExpectedIngredient[];
    /** 카테고리 힌트 */
    categoryHint: string;
  };
}

export const evalDataset: EvalCase[] = [
  // ───── 국/찌개 (6) ─────
  {
    // 더보기란에 정확한 재료+분량 + 시각분석에서 식초 확인
    name: "김치찌개 (백종원)",
    url: "https://www.youtube.com/watch?v=RVfSeUZ8XkY",
    expectedCriteria: {
      titleKeywords: ["김치", "찌개", "찜"],
      minSteps: 4,
      expectedIngredients: [
        { name: "돼지고기전지", amount: { value: 1, unit: "kg" } },
        { name: "신김치", amount: { value: 1.3, unit: "kg" } },
        { name: "양파", amount: { value: 0.5, unit: "개" } },
        { name: "대파", amount: { value: 1, unit: "컵" } },
        { name: "청양고추", amount: { value: 3, unit: "개" } },
        { name: "황설탕", amount: { value: 3, unit: "큰술" } },
        { name: "국간장", amount: { value: 2, unit: "큰술" } },
        { name: "된장", amount: { value: 1, unit: "큰술" } },
        { name: "간마늘", amount: { value: 1, unit: "큰술" } },
        { name: "굵은고춧가루", amount: { value: 2, unit: "큰술" } },
        { name: "물", amount: { value: 6, unit: "컵" } },
        { name: "식초", amount: null },
      ],
      categoryHint: "한식",
    },
  },
  {
    // 더보기란에 고추기름 + 순두부 페이스트 + 찌개 재료 상세 분량
    name: "순두부찌개 (Mrs마카롱여사)",
    url: "https://www.youtube.com/watch?v=iicQgrn5IDE",
    expectedCriteria: {
      titleKeywords: ["순두부"],
      minSteps: 4,
      expectedIngredients: [
        { name: "식용유", amount: { value: 2, unit: "컵" } },
        { name: "대파", amount: { value: 2, unit: "대" } },
        { name: "고춧가루", amount: { value: 1.5, unit: "컵" } },
        { name: "고추기름", amount: { value: 300, unit: "ml" } },
        { name: "소고기", amount: { value: 300, unit: "g" } },
        { name: "다진마늘", amount: { value: 100, unit: "g" } },
        { name: "간장", amount: { value: 3, unit: "T" } },
        { name: "참치액", amount: { value: 2, unit: "T" } },
        { name: "천일염", amount: { value: 3, unit: "T" } },
        { name: "후추", amount: { value: 1, unit: "t" } },
        { name: "물", amount: { value: 2, unit: "T" } },
        { name: "육수", amount: { value: 200, unit: "ml" } },
        { name: "순두부", amount: { value: 2, unit: "봉지" } },
        { name: "계란", amount: { value: 3, unit: "개" } },
      ],
      categoryHint: "한식",
    },
  },
  // 부대찌개 (Maangchi) 제외 — 영어 영상이라 한국어 레시피 추출 평가에 부적합
  {
    // 시각분석 화면 텍스트에서 분량 확인
    name: "고추장찌개 (1분요리 뚝딱이형)",
    url: "https://www.youtube.com/watch?v=w9cV4eGdT5Y",
    expectedCriteria: {
      titleKeywords: ["고추장찌개"],
      minSteps: 3,
      expectedIngredients: [
        { name: "식용유", amount: null },
        { name: "돼지고기", amount: { value: 100, unit: "g" } },
        { name: "고추장", amount: { value: 1, unit: "큰술" } },
        { name: "고춧가루", amount: { value: 1, unit: "큰술" } },
        { name: "물", amount: { value: 2, unit: "컵" } },
        { name: "감자", amount: null },
        { name: "대파", amount: null },
        { name: "양파", amount: null },
        { name: "애호박", amount: null },
        { name: "다진마늘", amount: { value: 1, unit: "큰술" } },
        { name: "국간장", amount: { value: 2, unit: "큰술" } },
        { name: "멸치액젓", amount: null },
        { name: "두부", amount: null },
        { name: "다시다", amount: { value: 0.5, unit: "큰술" } },
        { name: "팽이버섯", amount: null },
      ],
      categoryHint: "한식",
    },
  },
  {
    // 더보기란에 정확한 분량
    name: "미역국",
    url: "https://www.youtube.com/watch?v=xsTFsunt6-8",
    expectedCriteria: {
      titleKeywords: ["미역국"],
      minSteps: 3,
      expectedIngredients: [
        { name: "소고기", amount: { value: 100, unit: "g" } },
        { name: "미역", amount: { value: 10, unit: "g" } },
        { name: "참기름", amount: { value: 2, unit: "큰술" } },
        { name: "국간장", amount: { value: 3, unit: "큰술" } },
        { name: "물", amount: { value: 1.3, unit: "L" } },
        { name: "다진마늘", amount: { value: 0.67, unit: "큰술" } },
        { name: "멸치액젓", amount: { value: 1.5, unit: "큰술" } },
      ],
      categoryHint: "한식",
    },
  },

  // ───── 볶음/구이/찜 (6) ─────
  {
    // 시각분석 화면 텍스트에서 분량 확인
    name: "제육볶음 (류수영)",
    url: "https://www.youtube.com/watch?v=oe_WhcK2X4Q",
    expectedCriteria: {
      titleKeywords: ["제육", "볶음"],
      minSteps: 3,
      expectedIngredients: [
        { name: "돼지고기", amount: null },
        { name: "설탕", amount: { value: 2, unit: "큰술" } },
        { name: "간장", amount: { value: 3, unit: "큰술" } },
        { name: "고추장", amount: { value: 3, unit: "큰술" } },
        { name: "배음료", amount: null },
        { name: "마늘", amount: { value: 1, unit: "큰술" } },
        { name: "식초", amount: { value: 2, unit: "큰술" } },
        { name: "대파", amount: null },
        { name: "양파", amount: null },
        { name: "소금", amount: null },
        { name: "참기름", amount: null },
        { name: "후추", amount: null },
      ],
      categoryHint: "한식",
    },
  },
  {
    // 더보기란 분량 + 시각분석에서 양조간장 확인
    name: "오징어볶음",
    url: "https://www.youtube.com/watch?v=sT5KsSpq8w4",
    expectedCriteria: {
      titleKeywords: ["오징어", "볶음"],
      minSteps: 4,
      expectedIngredients: [
        { name: "오징어", amount: { value: 1.5, unit: "마리" } },
        { name: "대파", amount: { value: 1, unit: "대" } },
        { name: "양파", amount: { value: 1, unit: "개" } },
        { name: "마늘", amount: { value: 10, unit: "알" } },
        { name: "청양고추", amount: { value: 3, unit: "개" } },
        { name: "고춧가루", amount: { value: 3, unit: "T" } },
        { name: "설탕", amount: { value: 3, unit: "T" } },
        { name: "간장", amount: { value: 4, unit: "T" } },
        { name: "고추장", amount: { value: 1, unit: "T" } },
        { name: "식용유", amount: null },
        { name: "참기름", amount: null },
        { name: "통깨", amount: null },
      ],
      categoryHint: "한식",
    },
  },
  {
    // 시각분석 화면 텍스트에서 분량 확인
    name: "닭강정",
    url: "https://www.youtube.com/watch?v=Fvuy-rO5QUo",
    expectedCriteria: {
      titleKeywords: ["닭", "강정"],
      minSteps: 4,
      expectedIngredients: [
        { name: "닭다리", amount: null },
        { name: "꽈리고추", amount: null },
        { name: "양조간장", amount: { value: 4, unit: "스푼" } },
        { name: "흑설탕", amount: { value: 1, unit: "스푼" } },
        { name: "물엿", amount: { value: 2, unit: "스푼" } },
        { name: "다진마늘", amount: { value: 1, unit: "스푼" } },
        { name: "짜장가루", amount: { value: 1, unit: "스푼" } },
        { name: "맛술", amount: { value: 4, unit: "스푼" } },
        { name: "참기름", amount: { value: 1, unit: "스푼" } },
        { name: "식혜", amount: { value: 200, unit: "mL" } },
        { name: "통깨", amount: null },
      ],
      categoryHint: "한식",
    },
  },

  // ───── 밥 (3) ─────
  {
    // 시각분석 화면 텍스트에서 분량 확인
    name: "봄동비빔밥 (김대석 셰프)",
    url: "https://www.youtube.com/watch?v=s4yHtjJEjc0",
    expectedCriteria: {
      titleKeywords: ["봄동", "비빔밥"],
      minSteps: 3,
      expectedIngredients: [
        { name: "봄동", amount: { value: 1, unit: "포기" } },
        { name: "고춧가루", amount: { value: 3, unit: "스푼" } },
        { name: "다진마늘", amount: { value: 1, unit: "스푼" } },
        { name: "까나리액젓", amount: { value: 1, unit: "스푼" } },
        { name: "진간장", amount: { value: 2, unit: "스푼" } },
        { name: "매실청", amount: { value: 1, unit: "스푼" } },
        { name: "물엿", amount: { value: 0.5, unit: "스푼" } },
        { name: "통깨", amount: { value: 1, unit: "스푼" } },
        { name: "계란", amount: { value: 1, unit: "개" } },
        { name: "식용유", amount: null },
        { name: "소금", amount: null },
        { name: "참기름", amount: null },
        { name: "밥", amount: null },
      ],
      categoryHint: "한식",
    },
  },
  {
    // 더보기란에 정확한 분량
    name: "된장솥밥",
    url: "https://www.youtube.com/watch?v=klFhbUssB60",
    expectedCriteria: {
      titleKeywords: ["된장", "솥밥", "술밥"],
      minSteps: 3,
      expectedIngredients: [
        { name: "차돌박이", amount: { value: 200, unit: "g" } },
        { name: "두부", amount: { value: 0.5, unit: "모" } },
        { name: "애호박", amount: { value: 0.33, unit: "개" } },
        { name: "양파", amount: { value: 0.5, unit: "개" } },
        { name: "대파", amount: { value: 1, unit: "대" } },
        { name: "다진마늘", amount: { value: 1, unit: "큰술" } },
        { name: "된장", amount: { value: 2, unit: "큰술" } },
        { name: "고추장", amount: { value: 1, unit: "큰술" } },
        { name: "고춧가루", amount: { value: 2, unit: "큰술" } },
        { name: "물", amount: { value: 500, unit: "ml" } },
        { name: "굴소스", amount: { value: 1, unit: "큰술" } },
        { name: "참치액젓", amount: { value: 1, unit: "큰술" } },
      ],
      categoryHint: "한식",
    },
  },

  // ───── 면 (5) ─────
  {
    // 더보기란에 상세 분량 (고기 밑간 + 당면양념 포함)
    name: "잡채 (딸을위한레시피)",
    url: "https://www.youtube.com/watch?v=Ryk_6X-ZvO0",
    expectedCriteria: {
      titleKeywords: ["잡채", "당면"],
      minSteps: 4,
      expectedIngredients: [
        { name: "당면", amount: { value: 300, unit: "g" } },
        { name: "돼지고기", amount: { value: 300, unit: "g" } },
        { name: "당근", amount: { value: 150, unit: "g" } },
        { name: "파프리카", amount: { value: 0.5, unit: "개" } },
        { name: "양파", amount: { value: 200, unit: "g" } },
        { name: "표고버섯", amount: { value: 150, unit: "g" } },
        { name: "시금치", amount: { value: 180, unit: "g" } },
        { name: "간장", amount: null },
        { name: "설탕", amount: null },
        { name: "맛술", amount: { value: 2, unit: "큰술" } },
        { name: "다진마늘", amount: { value: 0.5, unit: "큰술" } },
        { name: "참기름", amount: null },
        { name: "후추", amount: null },
        { name: "식용유", amount: { value: 3, unit: "큰술" } },
        { name: "소금", amount: null },
        { name: "물엿", amount: { value: 5, unit: "큰술" } },
        { name: "굴소스", amount: { value: 1, unit: "큰술" } },
      ],
      categoryHint: "한식",
    },
  },
  {
    // 더보기란에 정확한 분량
    name: "짜장면 (이연복)",
    url: "https://www.youtube.com/watch?v=yHjFmePbqmk",
    expectedCriteria: {
      titleKeywords: ["짜장", "라면"],
      minSteps: 4,
      expectedIngredients: [
        { name: "짜장라면", amount: { value: 3, unit: "개" } },
        { name: "돼지고기", amount: { value: 100, unit: "g" } },
        { name: "양파", amount: null },
        { name: "애호박", amount: null },
        { name: "대파", amount: null },
        { name: "마늘", amount: null },
        { name: "식용유", amount: null },
        { name: "간장", amount: null },
      ],
      categoryHint: "중식",
    },
  },
  {
    // 더보기란에 정확한 g 단위 분량
    name: "짬뽕 (매일맛나)",
    url: "https://www.youtube.com/watch?v=ebpEZCEolRk",
    expectedCriteria: {
      titleKeywords: ["짬뽕"],
      minSteps: 4,
      expectedIngredients: [
        { name: "중화면", amount: { value: 250, unit: "g" } },
        { name: "배추", amount: { value: 110, unit: "g" } },
        { name: "양파", amount: { value: 0.25, unit: "개" } },
        { name: "부추", amount: { value: 35, unit: "g" } },
        { name: "표고버섯", amount: { value: 5, unit: "개" } },
        { name: "대파", amount: { value: 40, unit: "g" } },
        { name: "간돼지고기", amount: { value: 100, unit: "g" } },
        { name: "두반장", amount: { value: 25, unit: "g" } },
        { name: "고춧가루", amount: { value: 10, unit: "g" } },
        { name: "간장", amount: { value: 8, unit: "g" } },
        { name: "치킨스톡", amount: { value: 5, unit: "g" } },
        { name: "굴소스", amount: { value: 5, unit: "g" } },
        { name: "전분가루", amount: { value: 25, unit: "g" } },
        { name: "물", amount: { value: 700, unit: "ml" } },
        { name: "식용유", amount: null },
      ],
      categoryHint: "중식",
    },
  },
  {
    // 더보기란에 재료+분량
    name: "볶음우동 (하루한끼)",
    url: "https://www.youtube.com/watch?v=ienGoTyboNE",
    expectedCriteria: {
      titleKeywords: ["볶음우동"],
      minSteps: 3,
      expectedIngredients: [
        { name: "우동", amount: null },
        { name: "양배추", amount: null },
        { name: "양파", amount: null },
        { name: "마늘", amount: null },
        { name: "굴소스", amount: { value: 1, unit: "스푼" } },
        { name: "진간장", amount: { value: 1, unit: "스푼" } },
        { name: "참기름", amount: { value: 1, unit: "스푼" } },
        { name: "고춧가루", amount: { value: 0.5, unit: "스푼" } },
        { name: "설탕", amount: { value: 0.5, unit: "스푼" } },
        { name: "당근", amount: null },
        { name: "대파", amount: null },
        { name: "식용유", amount: null },
        { name: "후추", amount: null },
        { name: "마요네즈", amount: null },
      ],
      categoryHint: "일식",
    },
  },
  {
    // 더보기란에 상세 분량 (멸치육수 + 양념장 + 국수)
    name: "멸치국수",
    url: "https://www.youtube.com/watch?v=FI6iypOkNUg",
    expectedCriteria: {
      titleKeywords: ["멸치국수"],
      minSteps: 5,
      expectedIngredients: [
        { name: "디포리", amount: { value: 0.67, unit: "컵" } },
        { name: "육수용멸치", amount: { value: 1.5, unit: "컵" } },
        { name: "절단다시마", amount: { value: 5, unit: "장" } },
        { name: "물", amount: { value: 3, unit: "L" } },
        { name: "양파", amount: { value: 0.5, unit: "개" } },
        { name: "대파", amount: { value: 1, unit: "대" } },
        { name: "맛술", amount: { value: 0.5, unit: "컵" } },
        { name: "국간장", amount: { value: 3, unit: "큰술" } },
        { name: "꽃소금", amount: null },
        { name: "소면", amount: null },
        { name: "부추", amount: { value: 20, unit: "g" } },
        { name: "청양고추", amount: { value: 1, unit: "개" } },
        { name: "홍고추", amount: { value: 1, unit: "개" } },
        { name: "간마늘", amount: { value: 1, unit: "큰술" } },
        { name: "깨소금", amount: { value: 3, unit: "큰술" } },
        { name: "고춧가루", amount: { value: 1, unit: "큰술" } },
        { name: "황설탕", amount: { value: 0.33, unit: "큰술" } },
        { name: "진간장", amount: { value: 0.5, unit: "컵" } },
        { name: "참기름", amount: { value: 2, unit: "큰술" } },
        { name: "표고버섯", amount: { value: 0.5, unit: "개" } },
        { name: "당근", amount: { value: 30, unit: "g" } },
        { name: "애호박", amount: { value: 30, unit: "g" } },
        { name: "달걀", amount: { value: 1, unit: "개" } },
        { name: "김가루", amount: null },
        { name: "통단무지", amount: { value: 0.25, unit: "개" } },
      ],
      categoryHint: "한식",
    },
  },

  // ───── 양식 (2) ─────
  {
    // 시각분석 화면 텍스트에서 분량 확인 — 여러 파스타 레시피 모음이라 대표값 사용
    name: "원팬 파스타 (어남선생)",
    url: "https://www.youtube.com/watch?v=UUOpe_sTKzA",
    expectedCriteria: {
      titleKeywords: ["원팬", "파스타"],
      minSteps: 3,
      expectedIngredients: [
        { name: "파스타면", amount: null },
        { name: "버터", amount: null },
        { name: "우유", amount: null },
        { name: "물", amount: null },
        { name: "소금", amount: null },
        { name: "참치액", amount: null },
        { name: "마늘", amount: null },
        { name: "후추", amount: null },
        { name: "트러플오일", amount: null },
        { name: "홀토마토", amount: null },
        { name: "간장", amount: null },
        { name: "설탕", amount: null },
      ],
      categoryHint: "양식",
    },
  },
  {
    // GT 시각분석 확인 — 봉골레 수제비
    name: "봉골레 파스타 (흑백요리사)",
    url: "https://www.youtube.com/watch?v=-KTb3zivHXk",
    expectedCriteria: {
      titleKeywords: ["봉골레", "수제비"],
      minSteps: 4,
      expectedIngredients: [
        { name: "밀가루", amount: null },
        { name: "물", amount: null },
        { name: "조개", amount: null },
        { name: "올리브유", amount: null },
        { name: "마늘", amount: null },
        { name: "파슬리", amount: null },
        { name: "버터", amount: null },
        { name: "소금", amount: null },
      ],
      categoryHint: "양식",
    },
  },

  // ───── 중식 (1 추가) ─────
  {
    // GT 없음
    name: "탕수육",
    url: "https://www.youtube.com/watch?v=3taTKh1sQTY",
    expectedCriteria: {
      titleKeywords: ["탕수육"],
      minSteps: 4,
      expectedIngredients: [
        { name: "돼지고기", amount: null },
        { name: "전분", amount: null },
        { name: "식초", amount: null },
        { name: "설탕", amount: null },
        { name: "간장", amount: null },
        { name: "양파", amount: null },
      ],
      categoryHint: "중식",
    },
  },

  // ───── 분식 (2) ─────
  {
    // 더보기란에 정확한 분량
    name: "김밥 (후딱레시피)",
    url: "https://www.youtube.com/watch?v=3cdfYsC1b9U",
    expectedCriteria: {
      titleKeywords: ["김밥"],
      minSteps: 4,
      expectedIngredients: [
        { name: "햄", amount: { value: 5, unit: "줄" } },
        { name: "맛살", amount: { value: 3, unit: "줄" } },
        { name: "부추", amount: null },
        { name: "당근", amount: null },
        { name: "식용유", amount: null },
        { name: "계란", amount: { value: 4, unit: "개" } },
        { name: "밥", amount: { value: 130, unit: "g" } },
        { name: "맛소금", amount: { value: 0.5, unit: "작은술" } },
        { name: "참깨", amount: null },
        { name: "참기름", amount: null },
        { name: "김", amount: { value: 1, unit: "장" } },
        { name: "단무지", amount: { value: 2, unit: "줄" } },
      ],
      categoryHint: "분식",
    },
  },
  {
    // 더보기란에 분량 있음 (밥수저 계량)
    name: "떡볶이",
    url: "https://www.youtube.com/watch?v=roA-HHX9-GU",
    expectedCriteria: {
      titleKeywords: ["떡볶이"],
      minSteps: 3,
      expectedIngredients: [
        { name: "떡", amount: { value: 500, unit: "g" } },
        { name: "어묵", amount: { value: 3, unit: "장" } },
        { name: "대파", amount: { value: 1, unit: "대" } },
        { name: "식용유", amount: { value: 2, unit: "큰술" } },
        { name: "고운고춧가루", amount: { value: 2, unit: "큰술" } },
        { name: "고추장", amount: { value: 3, unit: "큰술" } },
        { name: "진간장", amount: { value: 2, unit: "큰술" } },
        { name: "설탕", amount: { value: 3, unit: "큰술" } },
        { name: "카레가루", amount: null },
        { name: "달걀", amount: null },
        { name: "물", amount: { value: 500, unit: "ml" } },
      ],
      categoryHint: "분식",
    },
  },

  // ───── 반찬 (3) ─────
  {
    // 더보기란에 정확한 분량
    name: "멸치볶음 (양장금주부)",
    url: "https://www.youtube.com/watch?v=Kwig1QzyHUA",
    expectedCriteria: {
      titleKeywords: ["멸치볶음"],
      minSteps: 3,
      expectedIngredients: [
        { name: "잔멸치", amount: { value: 180, unit: "g" } },
        { name: "꽈리고추", amount: { value: 7, unit: "개" } },
        { name: "식용유", amount: { value: 3, unit: "큰술" } },
        { name: "진간장", amount: { value: 2, unit: "큰술" } },
        { name: "맛술", amount: { value: 2, unit: "큰술" } },
        { name: "마늘", amount: { value: 1, unit: "큰술" } },
        { name: "올리고당", amount: { value: 3, unit: "큰술" } },
        { name: "마요네즈", amount: { value: 1, unit: "큰술" } },
        { name: "들기름", amount: { value: 1, unit: "큰술" } },
        { name: "통깨", amount: null },
      ],
      categoryHint: "반찬",
    },
  },
  {
    // 시각분석 화면 텍스트에서 전체 분량 확인
    name: "어묵볶음 (이 남자의 cook)",
    url: "https://www.youtube.com/watch?v=-kbf5FixN28",
    expectedCriteria: {
      titleKeywords: ["어묵볶음"],
      minSteps: 3,
      expectedIngredients: [
        { name: "어묵", amount: { value: 250, unit: "g" } },
        { name: "양파", amount: { value: 0.5, unit: "개" } },
        { name: "청고추", amount: { value: 2, unit: "개" } },
        { name: "홍고추", amount: { value: 1, unit: "개" } },
        { name: "양조간장", amount: { value: 2, unit: "큰술" } },
        { name: "다진마늘", amount: { value: 1, unit: "큰술" } },
        { name: "설탕", amount: { value: 1, unit: "작은술" } },
        { name: "굴소스", amount: { value: 1, unit: "작은술" } },
        { name: "고춧가루", amount: { value: 1, unit: "작은술" } },
        { name: "물엿", amount: { value: 3, unit: "큰술" } },
        { name: "후추", amount: null },
        { name: "고추기름", amount: { value: 2, unit: "큰술" } },
        { name: "참기름", amount: { value: 1, unit: "큰술" } },
        { name: "통깨", amount: { value: 1, unit: "큰술" } },
      ],
      categoryHint: "반찬",
    },
  },
  {
    // 더보기란에 정확한 분량
    name: "무생채 (요리왕비룡)",
    url: "https://www.youtube.com/watch?v=jNXwHjwSRwY",
    expectedCriteria: {
      titleKeywords: ["무생채"],
      minSteps: 3,
      expectedIngredients: [
        { name: "무", amount: { value: 1.2, unit: "kg" } },
        { name: "고운고춧가루", amount: { value: 6, unit: "큰술" } },
        { name: "보통고춧가루", amount: { value: 4, unit: "큰술" } },
        { name: "설탕", amount: { value: 3, unit: "큰술" } },
        { name: "식초", amount: { value: 3, unit: "큰술" } },
        { name: "생강", amount: { value: 1, unit: "작은술" } },
        { name: "간마늘", amount: { value: 1, unit: "큰술" } },
        { name: "대파", amount: null },
      ],
      categoryHint: "반찬",
    },
  },
  // ───── 기타 (2) ─────
  {
    // GT: 호떡 맛집 모음 영상
    name: "호떡",
    url: "https://www.youtube.com/watch?v=Xggvz30l3Ao",
    expectedCriteria: {
      titleKeywords: ["호떡"],
      minSteps: 2,
      expectedIngredients: [
        { name: "반죽", amount: null },
        { name: "흑설탕", amount: null },
        { name: "씨앗", amount: null },
        { name: "마가린", amount: null },
      ],
      categoryHint: "디저트",
    },
  },
];
