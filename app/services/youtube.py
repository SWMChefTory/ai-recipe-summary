from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from app.models import *
from typing import List, Dict

def get_subtitles_and_lang_code(video_id: str):
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

        return subtitles, generated_lang_code

    except (NoTranscriptFound, TranscriptsDisabled):
        print("자막이 없거나 비활성화된 영상입니다.")
        return None, None
    except Exception as e:
        print("자막 추출 중 예외 발생:", e)
        return None, None

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
    