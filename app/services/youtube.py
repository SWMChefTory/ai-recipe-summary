import os

# Type imports for better type hints
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import requests

from app.constants import ErrorMessages, YouTubeConfig
from app.services.base import BaseService
from app.utils.language import normalize_language_code

if TYPE_CHECKING:
    from app.services.audio_extractor import AudioExtractor
    from app.services.caption_extractor import CaptionExtractor


class YouTubeService(BaseService):
    """YouTube 관련 서비스 (자막 추출, 영상 정보 조회)"""

    def __init__(
        self, 
        google_api_key: Optional[str] = None, 
        audio_service=None,
        caption_extractor: Optional["CaptionExtractor"] = None,
        audio_extractor: Optional["AudioExtractor"] = None
    ) -> None:
        super().__init__()
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        self.audio_service = audio_service
        self.caption_extractor = caption_extractor
        self.audio_extractor = audio_extractor

    def extract_captions_with_language(self, video_id: str) -> Optional[Tuple[List[Dict], str]]:
        """3단계 fallback으로 자막과 언어 코드를 추출합니다.
        
        1단계: YouTube Transcript API
        2단계: yt-dlp로 자막 다운로드  
        3단계: 오디오 추출 후 STT
        """
        try:
            # 1단계: YouTube Transcript API 시도
            if self.caption_extractor:
                transcript_result = self.caption_extractor.extract_captions(video_id)
                if transcript_result:
                    self.logger.info("YouTube Transcript API로 자막 추출 성공")
                    return transcript_result

            # 2단계: yt-dlp로 자막 다운로드 시도
            if self.caption_extractor:
                ytdlp_result = self.caption_extractor.extract_captions_with_ytdlp(video_id)
                if ytdlp_result:
                    self.logger.info("yt-dlp로 자막 추출 성공")
                    return ytdlp_result

            # 3단계: 오디오 추출 후 STT로 대체
            self.logger.info("자막 파일이 없어 오디오 STT로 대체")
            return self._extract_captions_from_audio(video_id)

        except Exception as e:
            self.logger.exception(f"자막 추출 실패: {e}")
            return self._extract_captions_from_audio(video_id)

    def get_video_description(self, video_id: str) -> str:
        """YouTube 동영상의 설명란을 가져옵니다."""
        if not self.google_api_key:
            return ErrorMessages.GOOGLE_API_KEY_MISSING

        request_params = {
            "part": "snippet",
            "id": video_id,
            "key": self.google_api_key
        }

        try:
            response = requests.get(
                "https://www.googleapis.com/youtube/v3/videos", 
                params=request_params
            )
            response_data = response.json()
            return response_data["items"][0]["snippet"]["description"]

        except IndexError:
            return ErrorMessages.VIDEO_NOT_FOUND
        except KeyError as error:
            return f"{ErrorMessages.RESPONSE_KEY_MISSING}: {error}"

    def _extract_captions_from_audio(self, video_id: str) -> Optional[Tuple[List[Dict], str]]:
        """오디오 추출 후 STT를 사용해 자막을 생성합니다."""
        if not self.audio_service:
            self.logger.warning(ErrorMessages.AUDIO_SERVICE_NOT_CONFIGURED)
            return None
            
        if not self.audio_extractor:
            self.logger.warning("Audio extractor가 설정되지 않았습니다")
            return None
        
        audio_file_path = self.audio_extractor.extract_audio(video_id)
        if not audio_file_path:
            return None
            
        try:
            return self._process_audio_file(audio_file_path)
        finally:
            self.audio_service.cleanup_temp_file(audio_file_path)

    def _process_audio_file(self, audio_file_path: str) -> Optional[Tuple[List[Dict], str]]:
        """추출된 오디오 파일을 처리하여 자막과 언어 코드를 반환합니다."""
        if not self.audio_service:
            return None
            
        detected_language = self.audio_service.detect_language_from_audio(audio_file_path)
        language_code = normalize_language_code(
            detected_language or YouTubeConfig.DEFAULT_LANGUAGE
        )
        
        generated_captions = self.audio_service.extract_captions_from_audio(
            audio_file_path, language=language_code
        )
        
        if generated_captions:
            return generated_captions, language_code
        else:
            return None
    