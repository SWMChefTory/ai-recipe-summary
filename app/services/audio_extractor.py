import os
import tempfile
from typing import Dict, Optional

import yt_dlp
from pydub import AudioSegment

from app.constants import AudioConfig, YouTubeConfig
from app.services.base import BaseService


class AudioExtractor(BaseService):

    def extract_audio(self, video_id: str) -> Optional[str]:
        """안정성을 위한 4단계 대체 전략으로 오디오 추출"""
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        strategies = [
            self._get_primary_ydl_opts(),     # 고품질, 403 에러 방지
            self._get_fallback_ydl_opts(),    # 중품질, 다른 User-Agent 사용
            self._get_simple_ydl_opts(),      # 저품질, 높은 호환성
            self._get_minimal_ydl_opts(),     # 최대 호환성을 위한 최소 설정
        ]
        
        for i, ydl_opts in enumerate(strategies, 1):
            try:
                audio_path = self._try_extract_with_strategy(video_url, ydl_opts, video_id)
                if audio_path:
                    return audio_path
            except Exception as e:
                self._handle_extraction_error(e, i, len(strategies))
                    
        return None

    def _try_extract_with_strategy(self, video_url: str, ydl_opts: dict, video_id: str) -> Optional[str]:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            if not self._is_video_duration_valid(info):
                return None
            if not self._has_audio_formats(info):
                return None
                
            ydl.download([video_url])
            return self._process_downloaded_audio(video_id)

    def _is_video_duration_valid(self, info: Optional[dict]) -> bool:
        """영상 길이 검증"""
        duration = info.get('duration', 0) if info else 0
        if duration > YouTubeConfig.MAX_VIDEO_DURATION_SECONDS:
            self.logger.warning(f"영상이 너무 길어서({duration}초) 오디오 추출을 건너뜁니다")
            return False
        return True

    def _has_audio_formats(self, info: Optional[dict]) -> bool:
        """사용 가능한 오디오 포맷 확인"""
        if info and 'formats' in info:
            available_formats = [f.get('format_id') for f in info['formats'] if f.get('acodec') != 'none']
            if not available_formats:
                self.logger.warning("사용 가능한 오디오 포맷이 없습니다")
                return False
        return True

    def _process_downloaded_audio(self, video_id: str) -> Optional[str]:
        """다운로드된 오디오 파일 처리 및 압축"""
        audio_file_path = os.path.join(tempfile.gettempdir(), f"{video_id}.mp3")
        
        if not os.path.exists(audio_file_path):
            return None
            
        # OpenAI API 제한(25MB)을 위해 파일이 너무 크면 압축
        file_size = os.path.getsize(audio_file_path)
        if file_size > AudioConfig.MAX_FILE_SIZE_BYTES:
            compressed_path = self.compress_audio_file(audio_file_path)
            if compressed_path:
                return compressed_path
            else:
                os.remove(audio_file_path)
                return None
        
        return audio_file_path

    def _handle_extraction_error(self, error: Exception, attempt: int, total_attempts: int) -> None:
        """추출 에러 처리 및 로깅"""
        self.logger.warning(f"전략 {attempt} 실패: {error}")
        if attempt < total_attempts:
            self.logger.info("다음 전략으로 재시도합니다...")

    def compress_audio_file(self, audio_file_path: str) -> Optional[str]:
        """오디오 파일 압축"""
        try:
            audio = AudioSegment.from_mp3(audio_file_path)
            audio = audio.set_frame_rate(AudioConfig.COMPRESSED_SAMPLE_RATE)
            audio = audio.set_channels(AudioConfig.COMPRESSED_CHANNELS)
            
            compressed_path = audio_file_path.replace('.mp3', '_compressed.mp3')
            audio.export(compressed_path, format="mp3", bitrate=AudioConfig.COMPRESSED_BITRATE)
            
            if self._is_file_size_valid(compressed_path):
                os.remove(audio_file_path)
                return compressed_path
            else:
                os.remove(compressed_path)
                return None
                
        except Exception as e:
            self.logger.exception(f"오디오 압축 실패: {e}")
            return None

    def _is_file_size_valid(self, file_path: str) -> bool:
        """파일 크기 검증"""
        file_size = os.path.getsize(file_path)
        return file_size <= AudioConfig.MAX_FILE_SIZE_BYTES

    def _get_base_ydl_opts(self) -> dict:
        """기본 yt-dlp 옵션"""
        return {
            'outtmpl': os.path.join(tempfile.gettempdir(), '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'writeinfojson': False,
            'writecaptions': False,
            'writeautomaticsub': False,
        }

    def _get_primary_ydl_opts(self) -> dict:
        """고품질, 403 에러 방지"""
        base_opts = self._get_base_ydl_opts()
        base_opts.update({
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best[height<=480]/best',
            'postprocessors': [self._get_mp3_postprocessor('192')],
            'http_headers': self._get_full_headers(),
            'extractor_retries': 3,
            'file_access_retries': 3,
            'fragment_retries': 3,
            'retry_sleep_functions': {'extractor': lambda n: 2 ** n},
        })
        return base_opts
    
    def _get_fallback_ydl_opts(self) -> dict:
        """중품질, 다른 User-Agent 사용"""
        base_opts = self._get_base_ydl_opts()
        base_opts.update({
            'format': 'worstaudio[acodec!=none]/worstaudio/worst[height<=360]/worst',
            'postprocessors': [self._get_mp3_postprocessor('128')],
            'http_headers': {'User-Agent': YouTubeConfig.USER_AGENT},
            'extractor_retries': 2,
            'sleep_interval': 1,
        })
        return base_opts
    
    def _get_simple_ydl_opts(self) -> dict:
        """저품질, 높은 호환성"""
        base_opts = self._get_base_ydl_opts()
        base_opts.update({
            'format': '18/worst',
            'postprocessors': [self._get_mp3_postprocessor('96')],
            'ignoreerrors': False,
        })
        return base_opts
            
    def _get_minimal_ydl_opts(self) -> dict:
        """최대 호환성을 위한 최소 설정"""
        base_opts = self._get_base_ydl_opts()
        base_opts.update({
            'format': 'worst',
            'extract_flat': False,
            'postprocessor_args': ['-ar', str(AudioConfig.COMPRESSED_SAMPLE_RATE), '-ac', str(AudioConfig.COMPRESSED_CHANNELS)],
        })
        return base_opts

    def _get_mp3_postprocessor(self, quality: str) -> dict:
        """MP3 후처리기 설정"""
        return {
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': quality,
        }

    def _get_full_headers(self) -> dict:
        """차단 방지를 위한 브라우저 모방 헤더"""
        return {
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
        } 
        