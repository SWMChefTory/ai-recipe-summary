import json
import os
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

from app.services.base import BaseService
from app.utils.language import normalize_language_code


class CaptionExtractor(BaseService):

    def extract_captions(self, video_id: str) -> Optional[Tuple[List[Dict], str]]:
        """YouTube 자막 추출 - YouTube Transcript API 우선 시도 (수동영어 > 수동원본 > 자동영어 > 자동원본)"""
        try:
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # 원본 언어 감지
            original_lang = self._detect_original_language_from_transcripts(transcripts)
            
            # 우선순위에 따른 자막 추출 시도
            extraction_order = [
                ("manual", "en"),              # 1. 수동 자막 (영어)
                ("manual", original_lang),     # 2. 수동 자막 (원본 언어)
                ("auto", "en"),                # 3. 자동 자막 (영어)
                ("auto", original_lang),       # 4. 자동 자막 (원본 언어)
            ]
            
            for transcript_type, lang_code in extraction_order:
                if not lang_code:
                    continue
                
                # 중복 방지: 영어와 원본이 같으면 수동 영어만 시도
                if lang_code == "en" and original_lang == "en" and transcript_type == "manual":
                    # 첫 번째 시도이므로 진행
                    pass
                elif lang_code == original_lang and original_lang == "en" and transcript_type == "manual":
                    # 두 번째 시도인데 영어와 원본이 같으므로 건너뛰기
                    continue
                
                captions = self._fetch_transcript_by_type_and_language(transcripts, transcript_type, lang_code)
                if captions:
                    self.logger.info(f"YouTube Transcript API로 {transcript_type} {lang_code} 자막 추출 성공")
                    return captions, normalize_language_code(lang_code)
                
            return None

        except (NoTranscriptFound, TranscriptsDisabled):
            return None



    def _fetch_transcript_by_language(self, transcripts, target_lang_code: str) -> Optional[List[Dict]]:
        """직접 등록된 자막 우선, 그 다음 자동 생성된 자막"""
        manual_captions = self._try_fetch_manual_transcript(transcripts, target_lang_code)
        if manual_captions:
            return manual_captions
        return self._try_fetch_generated_transcript(transcripts, target_lang_code)

    def _try_fetch_manual_transcript(self, transcripts, target_lang_code: str) -> Optional[List[Dict]]:
        """직접 등록된 자막 가져오기 시도"""
        for transcript in transcripts:
            if not transcript.is_generated and transcript.language_code == target_lang_code:
                try:
                    return transcript.fetch().to_raw_data()
                except Exception as e:
                    self.logger.warning(f"직접 등록된 자막 가져오기 실패: {e}")
        return None

    def _try_fetch_generated_transcript(self, transcripts, target_lang_code: str) -> Optional[List[Dict]]:
        """자동 생성된 자막 가져오기 시도"""
        for transcript in transcripts:
            if transcript.is_generated and transcript.language_code == target_lang_code:
                try:
                    return transcript.fetch().to_raw_data()
                except Exception as e:
                    self.logger.warning(f"자동 생성된 자막 가져오기 실패: {e}")
        return None

    def _detect_original_language_from_transcripts(self, transcripts) -> Optional[str]:
        """트랜스크립트에서 원본 언어 감지"""
        # 수동 자막이 있는 언어들 중 첫 번째를 원본 언어로 간주
        for transcript in transcripts:
            if not transcript.is_generated:
                return transcript.language_code
        
        # 수동 자막이 없으면 자동 자막 중 첫 번째
        for transcript in transcripts:
            if transcript.is_generated:
                return transcript.language_code
                
        return None

    def _fetch_transcript_by_type_and_language(self, transcripts, transcript_type: str, lang_code: str) -> Optional[List[Dict]]:
        """타입(수동/자동)과 언어 코드로 자막 가져오기"""
        if transcript_type == "manual":
            return self._try_fetch_manual_transcript(transcripts, lang_code)
        elif transcript_type == "auto":
            return self._try_fetch_generated_transcript(transcripts, lang_code)
        return None

    def extract_captions_with_ytdlp(self, video_id: str) -> Optional[Tuple[List[Dict], str]]:
        """yt-dlp로 자막 추출 - 우선순위: 수동영어 > 수동원본 > 자동영어 > 자동원본"""
        # 먼저 영상의 원본 언어 감지
        original_lang = self._detect_video_language(video_id)
        
        extraction_methods = [
            ("manual", "en"),              # 1. 수동 자막 (영어)
            ("manual", original_lang),     # 2. 수동 자막 (원본 언어)
            ("auto", "en"),                # 3. 자동 자막 (영어)
            ("auto", original_lang),       # 4. 자동 자막 (원본 언어)
        ]
        
        for caption_type, language in extraction_methods:
            if not language:
                continue
            
            # 중복 방지: 영어와 원본이 같으면 중복 건너뛰기
            if language == original_lang and original_lang == "en" and caption_type == "manual":
                # 두 번째 시도인데 영어와 원본이 같으므로 건너뛰기
                continue
            
            result = self._try_extract_with_ytdlp(video_id, caption_type, language)
            if result:
                self.logger.info(f"yt-dlp로 자막 추출 성공: {caption_type} ({language})")
                return result
                
        return None

    def _try_extract_with_ytdlp(self, video_id: str, caption_type: str, language: str) -> Optional[Tuple[List[Dict], str]]:
        """yt-dlp로 특정 유형의 자막 추출 시도"""
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # yt-dlp 명령어 구성
                cmd = [
                  "yt-dlp",
                  "--skip-download",
                  "--write-info-json",
                  "--cookies", "/app/assets/yt_cookies/cookies.txt",
                  "--add-header", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                  "--add-header", "Referer: https://www.youtube.com/",
                  f"https://www.youtube.com/watch?v={video_id}"
]
                self.logger.info(f"[yt-dlp CMD] {' '.join(cmd)}")
                
                # 자막 유형에 따른 옵션 추가
                if caption_type == "manual":
                    cmd.append("--write-subs")
                    cmd.extend(["--sub-langs", language])
                else:  # auto
                    cmd.append("--write-auto-subs")
                    cmd.extend(["--sub-langs", language])
                
                cmd.extend(["-o", os.path.join(temp_dir, "%(title)s.%(ext)s")])
                
                # yt-dlp 실행
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    return None
                
                # 다운로드된 자막 파일 찾기
                captions_data = self._find_and_parse_subtitle_file(temp_dir)
                if captions_data:
                    # 언어 코드 추출 (파일명과 info.json에서)
                    lang_code = self._extract_language_from_files(temp_dir, language) or "ko"
                    return captions_data, normalize_language_code(lang_code)
                
                return None
                
            except subprocess.TimeoutExpired:
                self.logger.warning(f"yt-dlp 자막 추출 타임아웃: {video_id}")
                return None
            except Exception as e:
                self.logger.warning(f"yt-dlp 자막 추출 실패: {e}")
                return None

    def _find_and_parse_subtitle_file(self, temp_dir: str) -> Optional[List[Dict]]:
        """임시 디렉토리에서 자막 파일을 찾아 파싱"""
        for filename in os.listdir(temp_dir):
            if filename.endswith('.vtt'):
                file_path = os.path.join(temp_dir, filename)
                return self._parse_vtt_file(file_path)
            elif filename.endswith('.srt'):
                file_path = os.path.join(temp_dir, filename)
                return self._parse_srt_file(file_path)
        return None

    def _parse_vtt_file(self, file_path: str) -> Optional[List[Dict]]:
        """WebVTT 파일 파싱"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            captions = []
            lines = content.split('\n')
            i = 0
            
            while i < len(lines):
                if '-->' in lines[i]:
                    # 시간 정보 파싱
                    time_line = lines[i].strip()
                    start_time, end_time = time_line.split(' --> ')
                    start_sec = self._vtt_time_to_seconds(start_time)
                    end_sec = self._vtt_time_to_seconds(end_time)
                    
                    # 텍스트 수집
                    i += 1
                    text_lines = []
                    while i < len(lines) and lines[i].strip() != '':
                        # VTT 스타일 태그 제거
                        clean_text = self._clean_vtt_text(lines[i].strip())
                        if clean_text:
                            text_lines.append(clean_text)
                        i += 1
                    
                    if text_lines:
                        captions.append({
                            "start": start_sec,
                            "end": end_sec,
                            "text": ' '.join(text_lines)
                        })
                i += 1
                
            return captions if captions else None
            
        except Exception as e:
            self.logger.warning(f"VTT 파일 파싱 실패: {e}")
            return None

    def _parse_srt_file(self, file_path: str) -> Optional[List[Dict]]:
        """SRT 파일 파싱"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            captions = []
            blocks = content.strip().split('\n\n')
            
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    # 시간 정보 파싱 (두 번째 줄)
                    time_line = lines[1]
                    start_time, end_time = time_line.split(' --> ')
                    start_sec = self._srt_time_to_seconds(start_time)
                    end_sec = self._srt_time_to_seconds(end_time)
                    
                    # 텍스트 수집 (세 번째 줄부터)
                    text = ' '.join(lines[2:])
                    # SRT 텍스트도 정리
                    clean_text = self._clean_vtt_text(text)
                    
                    if clean_text:
                        captions.append({
                            "start": start_sec,
                            "end": end_sec,
                            "text": clean_text
                        })
                    
            return captions if captions else None
            
        except Exception as e:
            self.logger.warning(f"SRT 파일 파싱 실패: {e}")
            return None

    def _vtt_time_to_seconds(self, time_str: str) -> float:
        """WebVTT 시간 형식을 초로 변환 (00:00:00.000)"""
        try:
            time_str = time_str.strip()
            if '.' in time_str:
                time_part, ms_part = time_str.split('.')
                ms = float('0.' + ms_part)
            else:
                time_part = time_str
                ms = 0.0
                
            h, m, s = map(int, time_part.split(':'))
            return h * 3600 + m * 60 + s + ms
        except Exception:
            return 0.0

    def _srt_time_to_seconds(self, time_str: str) -> float:
        """SRT 시간 형식을 초로 변환 (00:00:00,000)"""
        try:
            time_str = time_str.strip().replace(',', '.')
            if '.' in time_str:
                time_part, ms_part = time_str.split('.')
                ms = float('0.' + ms_part)
            else:
                time_part = time_str
                ms = 0.0
                
            h, m, s = map(int, time_part.split(':'))
            return h * 3600 + m * 60 + s + ms
        except Exception:
            return 0.0

    def _extract_language_from_files(self, temp_dir: str, expected_lang: str) -> Optional[str]:
        """파일명과 info.json에서 언어 정보 추출"""
        try:
            # 먼저 파일명에서 언어 코드 추출 시도
            for filename in os.listdir(temp_dir):
                if filename.endswith(('.vtt', '.srt')):
                    # 파일명에서 언어 코드 추출 (예: video.ko.vtt, video.en.vtt)
                    parts = filename.split('.')
                    if len(parts) >= 3:
                        lang_from_filename = parts[-2]
                        if len(lang_from_filename) == 2:  # 언어 코드는 보통 2자리
                            return lang_from_filename
            
            # info.json에서 언어 정보 추출
            for filename in os.listdir(temp_dir):
                if filename.endswith('.info.json'):
                    file_path = os.path.join(temp_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        info = json.load(f)
                    
                    # 원본 언어 우선
                    if expected_lang == "any":
                        # 자막 정보에서 언어 코드 추출 (영어 > 한국어 우선)
                        if 'subtitles' in info and info['subtitles']:
                            langs = list(info['subtitles'].keys())
                            for preferred_lang in ['en', 'ko']:
                                if preferred_lang in langs:
                                    return preferred_lang
                            return langs[0]
                        elif 'automatic_captions' in info and info['automatic_captions']:
                            langs = list(info['automatic_captions'].keys())
                            for preferred_lang in ['en', 'ko']:
                                if preferred_lang in langs:
                                    return preferred_lang
                            return langs[0]
                    else:
                        return expected_lang
                    
            return None
        except Exception:
            return None

    def _clean_vtt_text(self, text: str) -> str:
        """VTT 스타일 태그 및 타임스탬프 제거"""
        import re

        # <c> 태그 제거
        text = re.sub(r'<c[^>]*>', '', text)
        text = re.sub(r'</c>', '', text)
        
        # 타임스탬프 태그 제거 (<00:00:09.240>)
        text = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', text)
        
        # 기타 HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)
        
        # 여러 공백을 하나로 정리
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    def _detect_video_language(self, video_id: str) -> Optional[str]:
        """영상의 원본 언어 감지"""
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 영상 정보만 가져오기
                cmd = [
                    "yt-dlp",
                    f"https://www.youtube.com/watch?v={video_id}",
                    "--dump-json",
                    "--no-download"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0:
                    import json
                    video_info = json.loads(result.stdout)
                    
                    # 1. 영상의 language 필드 확인
                    if 'language' in video_info and video_info['language']:
                        lang = video_info['language']
                        if len(lang) == 2:  # ISO 639-1 코드
                            return lang
                    
                    # 2. 자막 정보에서 가장 많이 사용되는 언어 확인
                    available_langs = []
                    if 'subtitles' in video_info:
                        available_langs.extend(video_info['subtitles'].keys())
                    if 'automatic_captions' in video_info:
                        available_langs.extend(video_info['automatic_captions'].keys())
                    
                    # 영어 > 한국어 우선, 그 다음 기타 언어
                    for preferred_lang in ['en', 'ko', 'ja', 'zh', 'zh-CN', 'zh-TW']:
                        if preferred_lang in available_langs:
                            return preferred_lang[:2]  # 2자리 코드로 통일
                    
                    # 그 외 언어 중 첫 번째
                    if available_langs:
                        return available_langs[0][:2]
                
                return None
                
            except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
                self.logger.warning(f"영상 언어 감지 실패: {e}")
                return "ko"  # 기본값으로 한국어 반환
 