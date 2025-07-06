import os
import tempfile
from typing import Dict, List, Optional, Tuple

import requests
import yt_dlp
from pydub import AudioSegment
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

from app.models import *
from app.services.base import BaseService


class YouTubeService(BaseService):
    """YouTube 관련 서비스"""

    def __init__(self, google_api_key: Optional[str] = None, audio_service=None):
        super().__init__()
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        self.audio_service = audio_service
        
        # 언어 코드 정규화 매핑 (2글자 ISO-639-1 형식)
        self.language_mapping = {
            # YouTube Transcript API에서 사용하는 형식들
            'korean': 'ko',
            'ko-kr': 'ko',
            'korean-kr': 'ko', 
            'korean_kr': 'ko',
            'english': 'en',
            'en-us': 'en',
            'en-gb': 'en',
            'english-us': 'en',
            'english-gb': 'en',
            'japanese': 'ja',
            'ja-jp': 'ja',
            'chinese': 'zh',
            'zh-cn': 'zh',
            'zh-tw': 'zh',
            'spanish': 'es',
            'es-es': 'es',
            'es-mx': 'es',
            'french': 'fr',
            'fr-fr': 'fr',
            'german': 'de',
            'de-de': 'de',
            'italian': 'it',
            'it-it': 'it',
            'portuguese': 'pt',
            'pt-br': 'pt',
            'pt-pt': 'pt',
            'russian': 'ru',
            'ru-ru': 'ru',
            'arabic': 'ar',
            'ar-sa': 'ar',
            'hindi': 'hi',
            'hi-in': 'hi',
            'dutch': 'nl',
            'swedish': 'sv',
            'norwegian': 'no',
            'danish': 'da',
            'finnish': 'fi',
            'polish': 'pl',
            'czech': 'cs',
            'hungarian': 'hu',
            'romanian': 'ro',
            'turkish': 'tr',
            'greek': 'el',
            'hebrew': 'he',
            'thai': 'th',
            'vietnamese': 'vi',
            'indonesian': 'id',
            'malay': 'ms',
            'filipino': 'tl',
            'tamil': 'ta',
            'telugu': 'te',
            'bengali': 'bn',
            'gujarati': 'gu',
            'marathi': 'mr',
            'punjabi': 'pa',
            'urdu': 'ur',
        }

    def _normalize_language_code(self, language: str) -> str:
        """언어 코드를 2글자 ISO-639-1 형식으로 정규화"""
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
        self.logger.warning(f"알 수 없는 언어 코드: {language}, 기본값 'ko' 사용")
        return 'ko'

    def get_subtitles_and_lang_code(self, video_id: str) -> Optional[Tuple[List[Dict], str]]:
        """
        주어진 YouTube 영상 ID에서 자막을 추출
        자막이 없을 경우 오디오 추출 -> OpenAI Whisper API로 자막 생성
        """
        try:
            # 1단계: 기존 자막 추출 시도
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)

            # 자동 생성된 자막 언어 코드 찾기
            generated_lang_code = self._find_generated_language_code(transcripts)
            if not generated_lang_code:
                self.logger.info("자동 생성 자막이 존재하지 않습니다.")
                return self._fallback_to_audio_extraction(video_id)

            # 해당 언어의 자막 가져오기
            subtitles = self._fetch_transcript_by_generated_lang_code(transcripts, generated_lang_code)
            if subtitles is None:
                self.logger.info(f"{generated_lang_code} 언어의 자막을 찾을 수 없습니다.")
                return self._fallback_to_audio_extraction(video_id)

            # 언어 코드를 2글자로 정규화
            normalized_lang_code = self._normalize_language_code(generated_lang_code)
            return subtitles, normalized_lang_code

        except (NoTranscriptFound, TranscriptsDisabled):
            self.logger.info("자막이 없거나 비활성화된 영상입니다. 오디오 추출을 시도합니다.")
            return self._fallback_to_audio_extraction(video_id)
        except Exception as e:
            self.logger.exception(f"자막 추출 중 예외 발생: {e}")
            return self._fallback_to_audio_extraction(video_id)

    def _find_generated_language_code(self, transcripts) -> Optional[str]:
        """자동으로 생성된 자막의 언어 코드를 반환"""
        for transcript in transcripts:
            if transcript.is_generated:
                return transcript.language_code
        return None

    def _fetch_transcript_by_generated_lang_code(
        self, transcripts, target_lang_code: str
    ) -> Optional[List[Dict]]:
        """
        지정된 언어 코드에 해당하는 자막 데이터 반환

        자막 선택 우선순위:
        1. 자동 생성된 자막의 언어코드에 해당하는 직접 등록된 자막
        2. 해당 언어의 자동 생성 자막
        """
        # 직접 등록된 자막 먼저 시도
        for transcript in transcripts:
            if not transcript.is_generated and transcript.language_code == target_lang_code:
                try:
                    return transcript.fetch().to_raw_data()
                except Exception as e:
                    self.logger.warning(f"직접 등록된 자막 가져오기 실패: {e}")
                    continue

        # 자동 생성된 자막 시도
        for transcript in transcripts:
            if transcript.is_generated and transcript.language_code == target_lang_code:
                try:
                    return transcript.fetch().to_raw_data()
                except Exception as e:
                    self.logger.warning(f"자동 생성된 자막 가져오기 실패: {e}")
                    continue

        return None

    def _fallback_to_audio_extraction(self, video_id: str) -> Optional[Tuple[List[Dict], str]]:
        """
        자막 추출 실패 시 오디오 추출 -> OpenAI Whisper API로 자막 생성
        """
        if not self.audio_service:
            self.logger.warning("AudioService가 설정되지 않아 오디오 추출을 수행할 수 없습니다.")
            return None
            
        self.logger.info("오디오 추출을 통한 자막 생성을 시도합니다.")
        
        # 1. YouTube 오디오 추출
        audio_file_path = self._extract_youtube_audio(video_id)
        if not audio_file_path:
            return None
            
        try:
            # 2. 언어 감지
            detected_lang = self.audio_service.detect_language_from_audio(audio_file_path)
            raw_language_code = detected_lang or "ko"  # 기본값: 한국어
            
            # 언어 코드를 2글자로 정규화
            language_code = self._normalize_language_code(raw_language_code)
            
            # 3. 자막 추출
            subtitles = self.audio_service.extract_subtitles_from_audio(
                audio_file_path, language=language_code
            )
            
            if subtitles:
                self.logger.info(f"오디오에서 {len(subtitles)}개의 자막을 추출했습니다. (언어: {language_code})")
                return subtitles, language_code
            else:
                self.logger.warning("오디오에서 자막을 추출할 수 없었습니다.")
                return None
                
        finally:
            # 4. 임시 파일 정리
            self.audio_service.cleanup_temp_file(audio_file_path)
            
    def _extract_youtube_audio(self, video_id: str) -> Optional[str]:
        """
        YouTube 영상에서 오디오를 추출하여 임시 파일로 저장
        여러 fallback 전략을 사용하여 403 에러 우회
        """
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # 여러 설정으로 시도
        strategies = [
            self._get_primary_ydl_opts(),
            self._get_fallback_ydl_opts(),
            self._get_simple_ydl_opts(),
            self._get_minimal_ydl_opts(),
        ]
        
        for i, ydl_opts in enumerate(strategies, 1):
            try:
                self.logger.info(f"오디오 추출 시도 {i}/{len(strategies)}")
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # 비디오 정보 추출
                    info = ydl.extract_info(video_url, download=False)
                    duration = info.get('duration', 0) if info else 0
                    
                    # 영상이 너무 길면 처리하지 않음 (예: 1시간 이상)
                    if duration > 3600:  # 3600초 = 1시간
                        self.logger.warning(f"영상이 너무 깁니다 ({duration}초). 오디오 추출을 생략합니다.")
                        return None
                    
                    # 사용 가능한 포맷 확인 및 조정
                    if info and 'formats' in info:
                        available_formats = [f.get('format_id') for f in info['formats'] if f.get('acodec') != 'none']
                        if not available_formats:
                            self.logger.warning("사용 가능한 오디오 포맷이 없습니다.")
                            continue
                        self.logger.info(f"사용 가능한 오디오 포맷: {len(available_formats)}개")
                    
                    # 오디오 다운로드
                    ydl.download([video_url])
                    
                    # 다운로드된 파일 경로 찾기
                    audio_file_path = os.path.join(tempfile.gettempdir(), f"{video_id}.mp3")
                    
                    if os.path.exists(audio_file_path):
                        # 파일 크기 확인 (OpenAI 제한: 25MB)
                        file_size = os.path.getsize(audio_file_path)
                        if file_size > 25 * 1024 * 1024:  # 25MB
                            # 파일이 너무 크면 압축 시도
                            compressed_path = self._compress_audio_file(audio_file_path)
                            if compressed_path:
                                return compressed_path
                            else:
                                self.logger.warning("오디오 파일이 너무 큽니다 (25MB 초과)")
                                os.remove(audio_file_path)
                                return None
                        
                        self.logger.info(f"오디오 추출 완료: {audio_file_path}")
                        return audio_file_path
                    else:
                        self.logger.error("오디오 파일을 찾을 수 없습니다.")
                        continue  # 다음 전략 시도
                        
            except Exception as e:
                self.logger.warning(f"전략 {i} 실패: {e}")
                if i < len(strategies):
                    self.logger.info("다음 전략으로 재시도합니다...")
                    continue
                else:
                    self.logger.exception("모든 오디오 추출 전략이 실패했습니다.")
                    
        return None
    
    def _get_primary_ydl_opts(self) -> dict:
        """기본 yt-dlp 설정 (403 에러 방지)"""
        return {
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best[height<=480]/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': tempfile.gettempdir() + '/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'writeinfojson': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            },
            'extractor_retries': 3,
            'file_access_retries': 3,
            'fragment_retries': 3,
            'retry_sleep_functions': {'extractor': lambda n: 2 ** n},
        }
    
    def _get_fallback_ydl_opts(self) -> dict:
        """대체 yt-dlp 설정 (다른 User-Agent 사용)"""
        return {
            'format': 'worstaudio[acodec!=none]/worstaudio/worst[height<=360]/worst',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
            'outtmpl': tempfile.gettempdir() + '/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
            'extractor_retries': 2,
            'sleep_interval': 1,
        }
    
    def _get_simple_ydl_opts(self) -> dict:
        """간단한 yt-dlp 설정 (최소 옵션)"""
        return {
            'format': '18/worst',  # 가장 호환성이 좋은 포맷
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '96',
            }],
            'outtmpl': tempfile.gettempdir() + '/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
        }
            
    def _get_minimal_ydl_opts(self) -> dict:
        """최소한의 yt-dlp 설정 (최대 호환성)"""
        return {
            'format': 'worst',  # 가장 낮은 품질 (가장 호환성 좋음)
            'outtmpl': tempfile.gettempdir() + '/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'postprocessor_args': ['-ar', '16000', '-ac', '1'],  # 16kHz 모노
        }
            
    def _compress_audio_file(self, audio_file_path: str) -> Optional[str]:
        """
        오디오 파일을 압축하여 OpenAI API 제한(25MB) 내로 맞춤
        """
        try:
            # pydub을 사용하여 오디오 압축
            audio = AudioSegment.from_mp3(audio_file_path)
            
            # 샘플 레이트를 낮춤 (24kHz -> 16kHz)
            audio = audio.set_frame_rate(16000)
            # 모노로 변환
            audio = audio.set_channels(1)
            
            # 압축된 파일 경로
            compressed_path = audio_file_path.replace('.mp3', '_compressed.mp3')
            
            # 압축하여 저장
            audio.export(compressed_path, format="mp3", bitrate="64k")
            
            # 압축 후 파일 크기 확인
            compressed_size = os.path.getsize(compressed_path)
            if compressed_size <= 25 * 1024 * 1024:  # 25MB
                # 원본 파일 삭제
                os.remove(audio_file_path)
                self.logger.info(f"오디오 파일 압축 완료: {compressed_path}")
                return compressed_path
            else:
                # 여전히 크면 압축된 파일도 삭제
                os.remove(compressed_path)
                self.logger.warning("압축 후에도 파일이 너무 큽니다.")
                return None
                
        except Exception as e:
            self.logger.exception(f"오디오 파일 압축 중 오류 발생: {e}")
            return None

    def get_video_description(self, video_id: str) -> str:
        """YouTube 영상의 설명을 가져오기"""
        if not self.google_api_key:
            return "ERROR: GOOGLE_API_KEY가 설정되지 않음"

        params = {
            "part": "snippet",
            "id": video_id,
            "key": self.google_api_key
        }

        try:
            response = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params)
            data = response.json()

            # 예외 발생 가능 구간
            return data["items"][0]["snippet"]["description"]

        except IndexError:
            return "ERROR: video ID가 잘못됐거나 결과가 없음"
        except KeyError as e:
            return f"ERROR: 응답에 예상된 키 없음 → {e}"


# 하위 호환성을 위한 함수들 (추후 제거 예정)
def get_subtitles_and_lang_code(video_id: str):
    """@deprecated: YouTubeService.get_subtitles_and_lang_code() 사용 권장"""
    service = YouTubeService()
    return service.get_subtitles_and_lang_code(video_id)


def get_youtube_description(video_id: str) -> str:
    """@deprecated: YouTubeService.get_video_description() 사용 권장"""
    service = YouTubeService()
    return service.get_video_description(video_id)
    