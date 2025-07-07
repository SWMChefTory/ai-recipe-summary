"""오디오 처리 서비스"""

import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from app.constants import AIConfig, AudioConfig, ErrorMessages
from app.services.base import BaseAIService
from app.utils.language import normalize_language_code

load_dotenv()


class AudioService(BaseAIService):
    """오디오 파일 처리 및 자막 추출 서비스"""

    def __init__(self, openai_client: Optional[OpenAI] = None, model_name: str = AIConfig.DEFAULT_MODEL) -> None:
        # OpenAI 클라이언트 설정
        if openai_client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                openai_client = OpenAI(api_key=api_key)
            else:
                self.logger.warning("OpenAI API 키가 .env 파일에 설정되지 않았습니다.")
        
        super().__init__(openai_client, model_name)
        self.whisper_model = AudioConfig.WHISPER_MODEL

    def extract_captions_from_audio(self, audio_file_path: str, language: str = AudioConfig.DEFAULT_LANGUAGE) -> Optional[List[Dict]]:
        """오디오 파일에서 자막 추출"""
        if not self._is_valid_audio_file(audio_file_path):
            return None

        try:
            normalized_language = normalize_language_code(language)
            captions = self._transcribe_audio(audio_file_path, normalized_language)
            
            if captions:
                self.logger.info(f"오디오에서 {len(captions)}개의 자막 세그먼트를 추출했습니다.")
                
            return captions

        except Exception as e:
            self.logger.exception(f"오디오 자막 추출 중 오류 발생: {e}")
            return None

    def detect_language_from_audio(self, audio_file_path: str) -> Optional[str]:
        """오디오에서 언어 감지"""
        if not self._is_valid_audio_file(audio_file_path):
            return None

        try:
            with open(audio_file_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    model=self.whisper_model,
                    file=audio_file,
                    response_format="verbose_json"
                )

            detected_language = getattr(transcription, 'language', None)
            if detected_language:
                normalized_language = normalize_language_code(detected_language)
                self.logger.info(f"감지된 언어: {detected_language} -> 정규화: {normalized_language}")
                return normalized_language
            
            return None

        except Exception as e:
            self.logger.exception(f"언어 감지 중 오류 발생: {e}")
            return None

    def cleanup_temp_file(self, file_path: str) -> None:
        """임시 파일 안전 삭제"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"임시 파일 삭제: {file_path}")
        except Exception as e:
            self.logger.warning(f"임시 파일 삭제 실패: {file_path}, 오류: {e}")

    def _is_valid_audio_file(self, audio_file_path: str) -> bool:
        """오디오 파일 유효성 검사"""
        if not os.path.exists(audio_file_path):
            self.logger.error(f"파일이 존재하지 않습니다: {audio_file_path}")
            return False
            
        # 파일 크기 확인 (OpenAI API 제한: 25MB)
        file_size = os.path.getsize(audio_file_path)
        if file_size > AudioConfig.MAX_FILE_SIZE_BYTES:
            self.logger.warning(f"{ErrorMessages.FILE_TOO_LARGE}: {audio_file_path}")
            return False
            
        return True

    def _transcribe_audio(self, audio_file_path: str, language: str) -> Optional[List[Dict]]:
        """오디오 파일을 텍스트로 변환 (세그먼트 단위)"""
        with open(audio_file_path, "rb") as audio_file:
            transcription = self.client.audio.transcriptions.create(
                model=self.whisper_model,
                file=audio_file,
                language=language,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )

        # 응답을 자막 형식으로 변환
        captions = []
        segments = getattr(transcription, 'segments', None)
        
        if segments:
            for segment in segments:
                captions.append({
                    "text": segment.text.strip(),
                    "start": segment.start,
                    "duration": segment.end - segment.start
                })
        else:
            # 세그먼트가 없는 경우, 전체 텍스트를 하나의 자막으로 처리
            text = getattr(transcription, 'text', None)
            if text:
                captions.append({
                    "text": text.strip(),
                    "start": 0.0,
                    "duration": 0.0
                })

        return captions if captions else None
            