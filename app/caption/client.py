import glob
import json
import logging
import os
import re
import subprocess
import tempfile
from typing import List

import webvtt

from app.caption.exception import CaptionErrorCode, CaptionException
from app.caption.schema import CaptionSegment


class CaptionClient:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _get_manual_captions_lang(self, video_id: str) -> str | None:
        url = f"https://www.youtube.com/watch?v={video_id}"

        '''
        yt-dlp 명령어 구성
        -J : 메타데이터를 JSON 형태로 출력
        --skip-download : 영상 파일은 다운로드하지 않음
        --extractor-args "youtube:skip=translated_subs" : 자동 번역된 자막은 제외
        --cookies : 쿠키 파일 지정
        url : 유튜브 영상 주소
        '''
        cmd = [
            "yt-dlp",
            "-J",
            "--skip-download",
            "--extractor-args", "youtube:skip=translated_subs",
            # TODO "--cookies", "/app/assets/yt_cookies/cookies.txt",
            url,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(res.stdout)

        # dict 구조 중 subtitles 키에 수동 자막 정보가 들어 있음
        manual_subs = data.get("subtitles") or {}

        # 한국어("ko") 우선, 없으면 영어("en"), 둘 다 없으면 None
        if "ko" in manual_subs:
            return "ko"
        if "en" in manual_subs:
            return "en"
        return None

    def _get_auto_captions_lang(self, video_id: str) -> str | None:
        url = f"https://www.youtube.com/watch?v={video_id}"

        '''
        yt-dlp 명령어 구성
        --skip-download : 영상 파일은 다운로드하지 않음
        --list-subs : 자동 생성 자막 리스트 출력
        --cookies : 쿠키 파일 지정
        url : 유튜브 영상 주소
        '''
        cmd = [
          "yt-dlp", 
          "--skip-download", 
          "--list-subs",
          # TODO "--cookies", "/app/assets/yt_cookies/cookies.txt",
          url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        output = res.stdout

        # 한국어("ko") 우선, 없으면 영어("en"), 둘 다 없으면 None
        if re.search(r"^ko-orig\s+", output, re.MULTILINE):
            return "ko-orig"
        if re.search(r"^en-orig\s+", output, re.MULTILINE):
            return "en-orig"
        return None

    def get_captions_lang_with_ytdlp(self, video_id: str) -> tuple[str, str]:
        manual_lang = self._get_manual_captions_lang(video_id)
        if manual_lang:
            return manual_lang, "manual"

        auto_lang = self._get_auto_captions_lang(video_id)
        if auto_lang:
            return auto_lang, "auto"

        raise CaptionException(CaptionErrorCode.CAPTION_NOT_FOUND)

    def extract_captions_with_ytdlp(self, video_id: str, caption_type: str, caption_lang: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                url = f"https://www.youtube.com/watch?v={video_id}"
                out_template = os.path.join(temp_dir, f"{video_id}.{caption_type}")


                '''
                yt-dlp 명령어 구성
                --skip-download : 영상 파일은 다운로드하지 않음
                --sub-format : 자막 형식 지정
                -o : 자막 파일 저장 경로
                --cookies : 쿠키 파일 지정
                --write-subs : 수동 자막 추출 or--write-auto-subs : 자동 자막 추출
                --sub-langs : 자막 언어 지정
                url : 유튜브 영상 주소
                '''
                cmd = [
                  "yt-dlp",
                  "--skip-download",
                  "--sub-format", "vtt",
                  "-o", out_template,
                  # TODO "--cookies", "/app/assets/yt_cookies/cookies.txt",
                ]
                
                if caption_type == "manual":
                    cmd.extend(["--write-subs", "--sub-langs", caption_lang])
                else:
                    cmd.extend(["--write-auto-subs", "--sub-langs", caption_lang])
                
                cmd.extend([url])

                self.logger.info(f"[yt-dlp] CMD: {' '.join(cmd)}")
                
                # yt-dlp 실행
                subprocess.run(cmd, capture_output=True, text=True)

                pattern = os.path.join(temp_dir, f"{video_id}.{caption_type}.*")
                files = glob.glob(pattern)

                # VTT 파일 파싱 -> 세그먼트 변환
                segments: List[CaptionSegment] = []
                for cue in webvtt.read(files[0]):
                    start = self._ts_to_seconds(cue.start)
                    end = self._ts_to_seconds(cue.end)
                    text = self._clean_vtt_text(cue.text)
                    if text:
                        segments.append(CaptionSegment(start=start, end=end, text=text))

                return segments

            except FileNotFoundError as e:
                self.logger.error(f"자막 다운로드 중 오류가 발생했습니다: {e}")
                raise CaptionException(CaptionErrorCode.CAPTION_DOWNLOAD_FAILED)

            except Exception as e:
                self.logger.error(f"자막 추출 중 오류가 발생했습니다: {e}")
                raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)

    def _ts_to_seconds(self, ts: str) -> float:
        # "HH:MM:SS.mmm" 형식으로 들어온 문자열을 ":" 기준으로 분리
        h, m, s = ts.split(":")      # h = "HH", m = "MM", s = "SS.mmm"

        # 초와 밀리초를 "." 기준으로 다시 분리
        sec, ms = s.split(".")       # sec = "SS", ms = "mmm"

        # 초 단위(float)로 환산
        return (int(h) * 3600) + (int(m) * 60) + int(sec) + (int(ms) / 1000.0)  

    def _clean_vtt_text(self, txt: str, join_lines: bool = False) -> str:
        # <c.colorE> 같은 스타일 태그, <i> 등의 HTML 태그 제거
        txt = re.sub(r"</?[^>]+>", "", txt)

        # 제어 문자 제거 (zero-width space, LTR/RTL marker 등)
        txt = re.sub(r"[\u200b\u200e\u200f]", "", txt)

        if join_lines:
            # 여러 줄을 하나의 문장으로 합치기 → 줄바꿈을 공백으로 대체
            txt = re.sub(r"\s*\n\s*", " ", txt)
            # 연속된 공백을 하나의 공백으로 축소
            txt = re.sub(r"\s{2,}", " ", txt)

        # 앞뒤 공백 제거 후 반환
        return txt.strip()