import { createTool } from "@mastra/core/tools";
import { z } from "zod";
import { YoutubeTranscript } from "youtube-transcript";

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

export const extractSubtitles = createTool({
  id: "extract-subtitles",
  description: "YouTube 영상의 자막을 시간순으로 추출합니다.",
  inputSchema: z.object({
    url: z.string().describe("YouTube 영상 URL"),
  }),
  outputSchema: z.object({
    subtitles: z.string().describe("시간순 자막 JSON 문자열"),
  }),
  execute: async ({ url }) => {
    try {
      const transcript = await YoutubeTranscript.fetchTranscript(url, {
        lang: "ko",
      });

      const subtitles = transcript.map((entry) => ({
        start: msToTimestamp(entry.offset),
        end: msToTimestamp(entry.offset + entry.duration),
        text: entry.text,
      }));

      return { subtitles: JSON.stringify(subtitles) };
    } catch (e) {
      // 한국어 자막 없으면 기본 자막 시도
      try {
        const transcript = await YoutubeTranscript.fetchTranscript(url);
        const subtitles = transcript.map((entry) => ({
          start: msToTimestamp(entry.offset),
          end: msToTimestamp(entry.offset + entry.duration),
          text: entry.text,
        }));
        return { subtitles: JSON.stringify(subtitles) };
      } catch {
        return { subtitles: "[]" };
      }
    }
  },
});
