import { Agent } from "@mastra/core/agent";
import { google } from "@ai-sdk/google";
import { analyzeYouTubeVideo } from "../../tools/analyze-video";

const instructions = `당신은 YouTube 요리 영상에서 레시피를 추출하는 에이전트입니다.

## 사용 방법
1. 사용자가 YouTube URL을 보내면, 반드시 analyzeYouTubeVideo 도구를 호출하세요.
2. 도구가 반환한 레시피 JSON을 그대로 사용자에게 전달하세요.
3. 절대로 도구 없이 레시피를 직접 생성하지 마세요.

## 중요
- YouTube URL이 아닌 다른 입력이 들어오면 YouTube URL을 요청하세요.
- 도구가 반환한 JSON을 수정하거나 편집하지 마세요. 그대로 출력하세요.`;

export const recipeExtractor = new Agent({
  id: "recipe-extractor",
  name: "Recipe Extractor",
  instructions,
  model: google("gemini-3.1-flash-lite-preview"),
  tools: {
    analyzeYouTubeVideo,
  },
});
