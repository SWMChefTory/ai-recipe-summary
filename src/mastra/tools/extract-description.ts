import { createTool } from "@mastra/core/tools";
import { z } from "zod";

function extractVideoId(url: string): string | null {
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

export const extractDescription = createTool({
  id: "extract-description",
  description: "YouTube 영상의 더보기란(설명)을 추출합니다.",
  inputSchema: z.object({
    url: z.string().describe("YouTube 영상 URL"),
  }),
  outputSchema: z.object({
    description: z.string().describe("영상 설명 텍스트"),
    title: z.string().describe("영상 제목"),
    channelName: z.string().describe("채널 이름"),
  }),
  execute: async ({ url }) => {
    const videoId = extractVideoId(url);
    if (!videoId) {
      return { description: "", title: "", channelName: "" };
    }

    try {
      // YouTube oEmbed API로 기본 정보 가져오기
      const oembedUrl = `https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${videoId}&format=json`;
      const oembedRes = await fetch(oembedUrl);
      const oembedData = (await oembedRes.json()) as {
        title: string;
        author_name: string;
      };

      // YouTube 페이지에서 description 추출
      const pageRes = await fetch(`https://www.youtube.com/watch?v=${videoId}`, {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
          "Accept-Language": "ko-KR,ko;q=0.9",
        },
      });
      const html = await pageRes.text();

      // ytInitialData에서 description 추출
      let description = "";
      const dataMatch = html.match(
        /var ytInitialData\s*=\s*({.+?});\s*<\/script>/s
      );
      if (dataMatch) {
        try {
          const data = JSON.parse(dataMatch[1]);
          // 영상 설명은 engagementPanels 또는 videoSecondaryInfoRenderer에 있음
          const contents =
            data?.contents?.twoColumnWatchNextResults?.results?.results
              ?.contents;
          if (contents) {
            for (const item of contents) {
              const secondary = item?.videoSecondaryInfoRenderer;
              if (secondary?.attributedDescription?.content) {
                description = secondary.attributedDescription.content;
                break;
              }
              // 또는 description runs에서 추출
              const descRuns =
                secondary?.description?.runs ||
                item?.expandedShelvesRenderer?.description?.runs;
              if (descRuns) {
                description = descRuns.map((r: { text: string }) => r.text).join("");
                break;
              }
            }
          }
        } catch {
          // JSON parse 실패 시 무시
        }
      }

      // 대안: meta description에서 추출
      if (!description) {
        const metaMatch = html.match(
          /<meta\s+name="description"\s+content="([^"]*?)"/
        );
        if (metaMatch) {
          description = metaMatch[1];
        }
      }

      // 대안: shortDescription에서 추출
      if (!description) {
        const shortDescMatch = html.match(
          /"shortDescription":"((?:[^"\\]|\\.)*)"/
        );
        if (shortDescMatch) {
          description = shortDescMatch[1]
            .replace(/\\n/g, "\n")
            .replace(/\\"/g, '"')
            .replace(/\\\\/g, "\\");
        }
      }

      return {
        description,
        title: oembedData.title || "",
        channelName: oembedData.author_name || "",
      };
    } catch {
      return { description: "", title: "", channelName: "" };
    }
  },
});
