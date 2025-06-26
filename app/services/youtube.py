from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from urllib.parse import urlparse, parse_qs
from app.models.schemas import SubtitleResponse
from typing import List, Dict

def get_video_id_from_youtube(url: str) -> str | None:
    parsed_url = urlparse(str(url))
    path_parts = parsed_url.path.strip("/").split("/")
    
    if len(path_parts) == 2 and path_parts[0] in ("shorts", "embed"):
        return path_parts[1]
    
    if parsed_url.path == "/watch":
        return parse_qs(parsed_url.query).get("v", [None])[0]
    
    if parsed_url.hostname == "youtu.be":
        return path_parts[0]
    
    return None

def get_subtitles(video_id: str) -> SubtitleResponse | None:
    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        
        for transcript in transcripts:
            if transcript.is_generated:
                lang_code = transcript.language_code

        for transcript in transcripts:
            if transcript.language_code == lang_code:
                subs: List[Dict] = transcript.fetch().to_raw_data()
                return SubtitleResponse(
                    video_id=video_id,
                    language=lang_code,
                    subtitles=subs
                )
        
        return None

    except (NoTranscriptFound, TranscriptsDisabled):
        print("자막이 없음 또는 비활성화된 영상입니다.")
        return None
    except Exception as e:
        print("자막 추출 중 오류:", e)
        return None
    