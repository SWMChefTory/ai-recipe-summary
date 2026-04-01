import "dotenv/config";
import { analyzeYouTubeVideo } from "../tools/analyze-video";

async function main() {
  try {
    const r = await analyzeYouTubeVideo.execute!({ url: "https://www.youtube.com/watch?v=w9cV4eGdT5Y" }, {} as any);
    console.log("SUCCESS");
    console.log(JSON.stringify(r).slice(0, 1000));
  } catch (e: any) {
    console.log("ERROR:", e.message?.slice(0, 500));
  }
}

main();
