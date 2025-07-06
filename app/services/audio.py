import os
import tempfile
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from app.services.base import BaseAIService

# .env 파일 로드
load_dotenv()


class AudioService(BaseAIService):
    """오디오 관련 서비스"""

    def __init__(self, openai_client: Optional[OpenAI] = None, model_name: str = "gpt-4o-mini"):
        # .env 파일에서 API 키 읽기
        if openai_client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                openai_client = OpenAI(api_key=api_key)
            else:
                self.logger.warning("OpenAI API 키가 .env 파일에 설정되지 않았습니다.")
        
        super().__init__(openai_client, model_name)
        self.whisper_model = "whisper-1"  # OpenAI Whisper API 모델
        
        # 언어 코드 매핑 (한국어 지원)
        self.language_mapping = {
            'korean': 'ko',
            'korean-kr': 'ko',
            'ko-kr': 'ko',
            'korean_kr': 'ko',
            'english': 'en',
            'en-us': 'en',
            'japanese': 'ja',
            'chinese': 'zh',
            'spanish': 'es',
            'french': 'fr',
            'german': 'de',
            'italian': 'it',
            'portuguese': 'pt',
            'russian': 'ru',
            'arabic': 'ar',
            'hindi': 'hi',
        }

    def _normalize_language_code(self, language: str) -> str:
        """언어 코드를 ISO-639-1 형식으로 변환"""
        if not language:
            return 'ko'  # 기본값
            
        # 소문자로 변환하고 공백 제거
        language_clean = language.lower().strip().replace('_', '-')
        
        # 매핑에서 찾기
        normalized = self.language_mapping.get(language_clean, language_clean)
        
        # 이미 2글자면 그대로 반환
        if len(normalized) == 2 and normalized.isalpha():
            return normalized
            
        # 하이픈이 있는 경우 첫 부분만 사용 (예: en-US -> en)
        if '-' in normalized:
            first_part = normalized.split('-')[0]
            if len(first_part) == 2 and first_part.isalpha():
                return first_part
                
        # 매핑되지 않은 경우 기본값 반환
        return 'ko'

    def extract_subtitles_from_audio(
        self, audio_file_path: str, language: str = "ko"
    ) -> Optional[List[Dict]]:
        """
        오디오 파일에서 자막을 추출합니다.
        
        Args:
            audio_file_path: 오디오 파일 경로
            language: 언어 코드 (예: 'ko', 'en')
            
        Returns:
            자막 데이터 리스트 또는 None
        """
        try:
            # 파일 크기 확인 (OpenAI API 제한: 25MB)
            if os.path.getsize(audio_file_path) > 25 * 1024 * 1024:
                self.logger.warning(f"오디오 파일 크기가 25MB를 초과합니다: {audio_file_path}")
                return None

            # 언어 코드 정규화
            normalized_language = self._normalize_language_code(language)
            
            # OpenAI Whisper API를 사용하여 자막 추출 (timestamp 포함)
            with open(audio_file_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    model=self.whisper_model,
                    file=audio_file,
                    language=normalized_language,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]  # segment 단위로 timestamp 추가
                )

            # 응답을 자막 형식으로 변환
            subtitles = []
            segments = getattr(transcription, 'segments', None)
            if segments:
                for segment in segments:
                    subtitles.append({
                        "text": segment.text.strip(),
                        "start": segment.start,
                        "duration": segment.end - segment.start
                    })
            else:
                # segments가 없는 경우, 전체 텍스트를 하나의 자막으로 처리
                text = getattr(transcription, 'text', None)
                if text:
                    subtitles.append({
                        "text": text.strip(),
                        "start": 0.0,
                        "duration": 0.0  # 전체 길이를 알 수 없으므로 0으로 설정
                    })

            self.logger.info(f"오디오에서 {len(subtitles)}개의 자막 세그먼트를 추출했습니다.")
            return subtitles

        except Exception as e:
            self.logger.exception(f"오디오 자막 추출 중 오류 발생: {e}")
            return None

    def detect_language_from_audio(self, audio_file_path: str) -> Optional[str]:
        """
        오디오에서 언어를 감지합니다.
        
        Args:
            audio_file_path: 오디오 파일 경로
            
        Returns:
            언어 코드 또는 None
        """
        try:
            # 파일 크기 확인
            if os.path.getsize(audio_file_path) > 25 * 1024 * 1024:
                self.logger.warning(f"오디오 파일 크기가 25MB를 초과합니다: {audio_file_path}")
                return None

            # OpenAI Whisper API를 사용하여 언어 감지
            with open(audio_file_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    model=self.whisper_model,
                    file=audio_file,
                    response_format="verbose_json"
                )

            # 언어 정보 확인
            detected_language = getattr(transcription, 'language', None)
            if detected_language:
                # 언어 코드를 2글자로 정규화
                normalized_language = self._normalize_language_code(detected_language)
                self.logger.info(f"감지된 언어: {detected_language} -> 정규화: {normalized_language}")
                return normalized_language
            
            return None

        except Exception as e:
            self.logger.exception(f"언어 감지 중 오류 발생: {e}")
            return None

    def cleanup_temp_file(self, file_path: str):
        """임시 파일을 정리합니다."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"임시 파일 삭제: {file_path}")
        except Exception as e:
            self.logger.warning(f"임시 파일 삭제 실패: {file_path}, 오류: {e}")
            