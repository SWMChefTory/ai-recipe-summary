from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from urllib.parse import urlparse, parse_qs
from app.models.schemas import SubtitleRequest, SubtitleResponse
from typing import List, Dict
from enum import Enum, auto

class YouTubeURLType(Enum):
    """YouTube URL의 유형을 정의하는 열거형"""
    WATCH = auto()   # https://www.youtube.com/watch?v=<video_id>
    SHORTS = auto()  # https://www.youtube.com/shorts/<video_id>
    EMBED = auto()   # https://www.youtube.com/embed/<video_id>
    SHARE = auto()   # https://youtu.be/<video_id>
    UNKNOWN = auto() # 위 유형에 해당하지 않는 경우

def get_youtube_url_type(url: str) -> YouTubeURLType:
    """주어진 URL을 분석하여 YouTube URL 유형을 반환"""
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.strip("/").split("/")

    if len(path_parts) == 2 and path_parts[0] == "shorts":
        return YouTubeURLType.SHORTS
    if len(path_parts) == 2 and path_parts[0] == "embed":
        return YouTubeURLType.EMBED
    if parsed_url.path == "/watch":
        return YouTubeURLType.WATCH
    if parsed_url.hostname == "youtu.be":
        return YouTubeURLType.SHARE

    return YouTubeURLType.UNKNOWN

def get_video_id_from_youtube(url: str) -> str | None:
    """다양한 유형의 YouTube URL에서 영상 ID를 추출"""
    parsed_url = urlparse(str(url))
    path_parts = parsed_url.path.strip("/").split("/")
    url_type = get_youtube_url_type(str(url))

    if url_type in (YouTubeURLType.SHORTS, YouTubeURLType.EMBED):
        return path_parts[1] if len(path_parts) == 2 else None
    
    elif url_type == YouTubeURLType.WATCH:
        return parse_qs(parsed_url.query).get("v", [None])[0]
    
    elif url_type == YouTubeURLType.SHARE:
        return path_parts[0] if path_parts else None

    return None  # 알 수 없는 형식



def get_subtitles(video_id: str) -> SubtitleResponse | None:
    """주어진 YouTube 영상 ID에서 자막을 추출"""
    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)

        # 자동 생성된 자막 언어 코드 찾기
        generated_lang_code = find_generated_language_code(transcripts)
        if not generated_lang_code:
            print("자동 생성 자막이 존재하지 않습니다.")
            return None # 자동 생성 자막이 존재하지 않는 경우 None을 반환

        # 해당 언어의 자막 가져오기
        subtitles = fetch_transcript_by_generated_lang_code(transcripts, generated_lang_code)
        if subtitles is None:
            print(f"{generated_lang_code} 언어의 자막을 찾을 수 없습니다.")
            return None # 자막이 없거나 비활성화된 경우 None을 반환

        return SubtitleResponse(
            video_id=video_id,
            language=generated_lang_code,
            subtitles=subtitles
        )

    except (NoTranscriptFound, TranscriptsDisabled):
        print("자막이 없거나 비활성화된 영상입니다.")
        return None
    except Exception as e:
        print("자막 추출 중 예외 발생:", e)
        return None

def find_generated_language_code(transcripts) -> str | None:
    """자동으로 생성된 자막의 언어 코드를 반환"""
    for transcript in transcripts:
        if transcript.is_generated:
            return transcript.language_code
    return None

def fetch_transcript_by_generated_lang_code(transcripts, target_lang_code: str) -> List[Dict] | None:
    """
    지정된 언어 코드에 해당하는 자막 데이터 반환

        자막 선택 우선순위:
        1. 자동 생성된 자막의 언어코드에 해당하는 직접 등록된 자막
        2. 해당 언어의 자동 생성 자막
    """
    for transcript in transcripts:
        if not transcript.is_generated and transcript.language_code == target_lang_code:
            return transcript.fetch().to_raw_data()

    for transcript in transcripts:
        if transcript.is_generated and transcript.language_code == target_lang_code:
            return transcript.fetch().to_raw_data()
    
    return None
    