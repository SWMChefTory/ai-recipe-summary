/**
 * YouTuber 프로필 - 레시피 추출에 도움되는 채널 특성
 */
export interface YoutuberProfile {
  channelId: string;
  channelName: string;
  characteristics: {
    /** 영상 스타일 */
    videoStyle: {
      avgLengthSeconds: number;
      editingPace: "very_fast" | "fast" | "moderate" | "slow";
      format: string; // e.g., "숏폼 요리", "브이로그형", "강의형" 등
    };
    /** 레시피 진행 패턴 */
    recipePresentation: {
      introStyle: string; // e.g., "훅으로 시작", "재료 먼저 소개" 등
      stepGranularity: "very_detailed" | "detailed" | "moderate" | "compressed";
      ingredientDetailLevel: "exact_measurements" | "approximate" | "minimal";
    };
    /** 팁/코멘트 제공자 패턴 */
    speakers: Array<{
      name: string; // e.g., "뚝딱이형", "잼민이"
      role: "main" | "sub" | "narrator";
      tipStyle: string; // e.g., "조리 중 팁", "대체재료 추천", "TTS 코멘트"
    }>;
    /** 대체 재료 추천 빈도 */
    substituteFrequency: "high" | "medium" | "low" | "none";
    /** 이 유튜버에게서 자주 나타나는 동적 필드 */
    dynamicFields: Array<{
      fieldName: string; // snake_case
      description: string;
      frequency: "always" | "often" | "sometimes" | "rare";
    }>;
    /** 기타 고유 특성 */
    uniqueTraits: string[];
  };
  /** 이 유튜버 영상에서 레시피 추출 시 적용할 가이드라인 */
  extractionGuidelines: string;
  /** 조사 일시 */
  researchedAt: string;
  /** 조사에 사용된 샘플 영상 수 */
  sampleVideoCount: number;
}

/**
 * 단계 내 참고 장면
 * - 사용자가 "이걸 어떻게 하지?"를 해결하기 위해 참고할 영상 구간
 * - 예: 올리브유 넣는 양, 파슬리 줄기 뜯는 방법 등
 */
export interface StepScene {
  /** 장면 라벨 (예: "마늘 편 써는 장면") */
  label: string;
  /** 시작 타임스탬프 HH:MM:SS.s (0.1초 단위) */
  start: string;
  /** 종료 타임스탬프 HH:MM:SS.s (0.1초 단위) */
  end: string;
}

/**
 * 레시피 단계
 */
export interface RecipeStep {
  /** 단계 순서 (1부터) */
  order: number;
  /** 단계 제목 (예: "마늘 손질") */
  title: string;
  /** 무엇을 해야 하는가 — 조리 지시 */
  description: string;
  /** 실용적인 요리 팁 (화자 귀속 필수) */
  tip?: string | string[];
  /** 알면 좋은 배경지식 */
  knowledge?: string;
  /** 이 단계에서 참고하면 좋은 핵심 조리 장면들 */
  scenes: StepScene[];
  /** 타이머 (초 단위) */
  timer_seconds?: number;
  /** 불 세기 (예: "센 불", "중약불") */
  heat_level?: string;
  /** 동적 필드 */
  [key: string]: unknown;
}

/**
 * 추출된 레시피 JSON 스키마
 */
export interface ExtractedRecipe {
  title: string;
  /** 요리 설명 */
  description?: string;
  /** 인분 수 */
  servings?: number;
  /** 조리 시간 (분) */
  cooking_time_minutes?: number;
  /** 난이도 */
  difficulty?: "쉬움" | "보통" | "어려움";
  /** 카테고리 (한식, 양식, 중식 등) */
  category?: string;
  ingredients: Array<{
    name: string;
    amount: {
      value: number | null;
      unit: string | null;
    };
    substitute?: string;
    [key: string]: unknown; // 동적 필드
  }>;
  tools: Array<{
    name: string;
    [key: string]: unknown; // 동적 필드
  }>;
  steps: RecipeStep[];
  /** 전체 요리에 대한 일반 팁 */
  general_tips?: string[];
  [key: string]: unknown; // 최상위 동적 필드
}

/**
 * YouTube 영상 정보
 */
export interface VideoInfo {
  videoId: string;
  title: string;
  channelName: string;
  channelId: string;
  description: string;
  duration: string;
}

/**
 * YouTube 트랜스크립트 세그먼트
 */
export interface TranscriptSegment {
  text: string;
  offset: number; // ms
  duration: number; // ms
}
