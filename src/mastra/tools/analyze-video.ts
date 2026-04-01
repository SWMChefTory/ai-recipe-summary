import { createTool } from "@mastra/core/tools";
import { z } from "zod";
import { google } from "@ai-sdk/google";
import { generateText } from "ai";
import { YoutubeTranscript } from "youtube-transcript";
import { loadPrompt } from "../prompts";

// ─── 유틸 ───

function msToTimestamp(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(
    2,
    "0"
  );
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
}

export function extractVideoId(url: string): string | null {
  const patterns = [
    /(?:youtube\.com\/watch\?v=)([^&\s]+)/,
    /(?:youtu\.be\/)([^?\s]+)/,
    /(?:youtube\.com\/embed\/)([^?\s]+)/,
    /(?:youtube\.com\/shorts\/)([^?\s]+)/,
  ];
  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match) return match[1];
  }
  return null;
}

// ─── 데이터 수집 (병렬) ───

export async function fetchSubtitles(url: string) {
  try {
    const transcript = await YoutubeTranscript.fetchTranscript(url, {
      lang: "ko",
    });
    return transcript.map((entry) => ({
      start: msToTimestamp(entry.offset),
      end: msToTimestamp(entry.offset + entry.duration),
      text: entry.text,
    }));
  } catch {
    try {
      const transcript = await YoutubeTranscript.fetchTranscript(url);
      return transcript.map((entry) => ({
        start: msToTimestamp(entry.offset),
        end: msToTimestamp(entry.offset + entry.duration),
        text: entry.text,
      }));
    } catch {
      return [];
    }
  }
}

export async function fetchDescription(url: string) {
  const videoId = extractVideoId(url);
  if (!videoId) return { description: "", title: "", channelName: "" };

  try {
    const oembedUrl = `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`;
    const oembedRes = await fetch(oembedUrl);
    const oembedData = (await oembedRes.json()) as {
      title: string;
      author_name: string;
    };

    const pageRes = await fetch(
      `https://www.youtube.com/watch?v=${videoId}`,
      {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
          "Accept-Language": "ko-KR,ko;q=0.9",
        },
      }
    );
    const html = await pageRes.text();

    let description = "";

    // shortDescription에서 추출
    const shortDescMatch = html.match(
      /"shortDescription":"((?:[^"\\]|\\.)*)"/
    );
    if (shortDescMatch) {
      description = shortDescMatch[1]
        .replace(/\\n/g, "\n")
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, "\\");
    }

    // 대안: meta description
    if (!description) {
      const metaMatch = html.match(
        /<meta\s+name="description"\s+content="([^"]*?)"/
      );
      if (metaMatch) description = metaMatch[1];
    }
    console.log("더보기 수집 완료");

    return {
      description,
      title: oembedData.title || "",
      channelName: oembedData.author_name || "",
    };
  } catch {
    return { description: "", title: "", channelName: "" };
  }
}

// ─── 프롬프트 ───

export const phase1Prompt = loadPrompt("phase1", "v1");
export const phase4Prompt = loadPrompt("phase4", "v1");

const node1Prompt = loadPrompt("node1-extract", "v3");
const node2Prompt = loadPrompt("node2-ingredients", "v3");
const node3Prompt = loadPrompt("node3-refine", "v3");
const node4Prompt = loadPrompt("node4-metadata", "v3");
const node5Prompt = loadPrompt("node5-scene", "v3");

function cleanJson(text: string): string {
  return text.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
}

// ─── Tool ───

export const analyzeYouTubeVideo = createTool({
  id: "analyze-youtube-video",
  description:
    "YouTube 요리 영상 URL을 받아 영상을 직접 분석하고 구조화된 레시피 JSON을 추출합니다. YouTube URL을 받으면 반드시 이 도구를 사용하세요.",
  inputSchema: z.object({
    url: z.string().describe("YouTube 영상 URL"),
  }),
  outputSchema: z.object({
    recipe: z.string().describe("추출된 레시피 JSON 문자열"),
  }),
  execute: async ({ url }) => {
    const videoId = extractVideoId(url);
    const normalizedUrl = videoId
      ? `https://www.youtube.com/watch?v=${videoId}`
      : url;

    // ─── 데이터 수집 (더보기란) ───
    console.log("[수집] 더보기란 수집...");

    const videoInfo = await fetchDescription(normalizedUrl);

    console.log(
      `[수집 완료] 더보기란: ${videoInfo.description.length}자`
    );

    // ─── 노드1 (Flash): 영상 → flat descriptions ───
    console.log("[노드1] 영상 분석...");

    const node1Result = await generateText({
      model: google("gemini-3-flash-preview"),
      providerOptions: {
        google: {
          thinkingConfig: {
            thinkingLevel: "high",
          },
        },
      },
      messages: [
        {
          role: "user",
          content: [
            { type: "file", data: normalizedUrl, mediaType: "video/mp4" },
            { type: "text", text: node1Prompt },
          ],
        },
      ],
    });

    const node1Json = cleanJson(node1Result.text);
    console.log("[노드1 완료] 초안 생성됨");

    // ─── 노드2 + 노드3 병렬 실행 ───
    console.log("[노드2+3] 재료 추출 + 장면 필터링 병렬...");

    const descriptionSummary = (() => {
      try {
        const parsed = JSON.parse(node1Json);
        return (parsed.descriptions || [])
          .map((d: any) => `- ${d.content}`)
          .join("\n");
      } catch {
        return node1Json;
      }
    })();

    async function withRetry<T>(fn: () => Promise<T>, retries = 3, delay = 5000): Promise<T> {
      for (let i = 0; i < retries; i++) {
        try { return await fn(); }
        catch (e: any) {
          if (i < retries - 1 && (e?.status === 429 || e?.message?.includes("high demand"))) {
            console.log(`  ⏳ 재시도 ${i + 1}/${retries} (${delay}ms 대기)...`);
            await new Promise(r => setTimeout(r, delay * (i + 1)));
            continue;
          }
          throw e;
        }
      }
      throw new Error("withRetry: unreachable");
    }

    // ─── 노드2 + 노드3 + 노드4 병렬 (노드3→5는 순차) ───

    const node2Promise = withRetry(() => generateText({
      model: google("gemini-2.5-flash"),
      prompt: `## 더보기란\n영상 제목: ${videoInfo.title}\n채널: ${videoInfo.channelName}\n설명:\n${videoInfo.description}\n\n## 레시피 초안 (description)\n${descriptionSummary}\n\n${node2Prompt}`,
    }));

    const node3Then5Promise = (async () => {
      // 노드3 (Pro): flat descriptions → step 분할
      console.log("[노드3] step 분할...");
      const node3Result = await withRetry(() => generateText({
        model: google("gemini-2.5-pro"),
        prompt: `## 조리 동작 목록 (시간순)\n${node1Json}\n\n${node3Prompt}`,
      }));
      const node3Json = cleanJson(node3Result.text);
      console.log("[노드3 완료]");

      // 노드5 (Pro): step + description → scene 추가
      console.log("[노드5] scene 생성...");
      const node5Result = await withRetry(() => generateText({
        model: google("gemini-2.5-pro"),
        prompt: `## 레시피 (scene 없음)\n${node3Json}\n\n${node5Prompt}`,
      }));
      console.log("[노드5 완료]");
      return node5Result;
    })();

    const node4Promise = (videoInfo.description.length > 0)
      ? generateText({
          model: google("gemini-3.1-flash-lite-preview"),
          prompt: `## 더보기란\n영상 제목: ${videoInfo.title}\n채널: ${videoInfo.channelName}\n설명:\n${videoInfo.description}\n\n${node4Prompt}`,
        })
      : generateText({
          model: google("gemini-3.1-flash-lite-preview"),
          messages: [
            {
              role: "user",
              content: [
                { type: "file", data: normalizedUrl, mediaType: "video/mp4" },
                { type: "text", text: node4Prompt },
              ],
            },
          ],
        });

    const [node2Result, node5Result, node4Result] = await Promise.all([
      node2Promise,
      node3Then5Promise,
      node4Promise,
    ]);

    console.log("[노드2+3→5+4 완료]");

    // ─── 합치기 ───
    const node2Parsed = JSON.parse(cleanJson(node2Result.text));
    const node5Parsed = JSON.parse(cleanJson(node5Result.text));
    const node4Parsed = JSON.parse(cleanJson(node4Result.text));
    const node1Parsed = JSON.parse(node1Json);

    const finalRecipe = {
      title: node4Parsed.title ?? "untitled",
      description: node4Parsed.description ?? null,
      servings: node4Parsed.servings ?? null,
      cookingTimeMinutes: node4Parsed.cookingTimeMinutes ?? null,
      difficulty: node4Parsed.difficulty ?? "보통",
      category: node4Parsed.category ?? "한식",
      ingredients: node2Parsed.ingredients ?? [],
      tools: node2Parsed.tools ?? [],
      steps: node5Parsed.steps ?? [],
      servingTip: node4Parsed.servingTip ?? null,
    };

    const recipeText = JSON.stringify(finalRecipe, null, 2);

    return { recipe: recipeText };
  },
});
