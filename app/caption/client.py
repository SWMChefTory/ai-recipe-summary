
import glob
import json
import logging
import os
import subprocess
import tempfile
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

import requests

from app.caption.enum import CaptionType
from app.caption.exception import CaptionErrorCode, CaptionException


class CaptionClient:
    def __init__(self):
        self.logger = logging.getLogger(__name__)


    def __get_video_info_json(self, video_id: str) -> dict:
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            cmd = [
                "yt-dlp",
                "-J",
                "--skip-download",
                "--retries", "2",
                "--cookies", "/app/assets/yt_cookies/cookies.txt",
                url,
            ]
            self.logger.info(f"[1차] yt-dlp 실행 명령어: {' '.join(cmd)}")
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return json.loads(res.stdout)
        except Exception as e:
            self.logger.error(f"info.json 파싱 중 오류가 발생했습니다. video_id={video_id}, err={e}")
            raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)


    def __extract_captions_info(self, video_info: dict, video_id: str) -> Tuple[str, str, CaptionType]:
        def is_translated_url(url: str) -> bool:
            q = parse_qs(urlparse(url).query or "")
            return "tlang" in q and q["tlang"]

        def pick_captions_info(mapping: dict) -> Optional[Tuple[str, str]]:
            for lang_code in ("ko", "en"):
                captions_info_list = mapping.get(lang_code)
                
                if not captions_info_list:
                    continue

                srt_captions_info = None
                for captions_info in captions_info_list:
                    ext = captions_info.get("ext")
                    download_url = captions_info.get("url")

                    if ext == "srt" and download_url and not is_translated_url(download_url):
                        srt_captions_info = captions_info
                        break

                if srt_captions_info:
                    return srt_captions_info["url"], lang_code
                
            return None

        manual_captions_info = video_info.get(CaptionType.MANUAL.value) or {}
        picked_captions_info = pick_captions_info(manual_captions_info)
        
        if picked_captions_info:
            return picked_captions_info[0], picked_captions_info[1], CaptionType.MANUAL

        auto_captions_info = video_info.get(CaptionType.AUTO.value) or {}
        picked_captions_info = pick_captions_info(auto_captions_info)

        if picked_captions_info:
            return picked_captions_info[0], picked_captions_info[1], CaptionType.AUTO

        self.logger.info(f"자막이 존재하지 않습니다. video_id={video_id}")
        raise CaptionException(CaptionErrorCode.CAPTION_NOT_FOUND)


    def __download_captions_from_url(self, download_url: str, timeout: int = 30) -> str:
        try:
            r = requests.get(download_url, timeout=timeout)
            r.raise_for_status()
            return r.text
        except Exception as e:
            self.logger.error(f"[1차] 자막 다운로드 중 오류가 발생했습니다. error={e}")
            return ""

    def __download_captions_from_ytdlp(self, video_id: str, captions_type: CaptionType, lang_code: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                url = f"https://www.youtube.com/watch?v={video_id}"
                out_template = os.path.join(temp_dir, f"{video_id}.{captions_type}")

                cmd = [
                    "yt-dlp",
                    "--skip-download",
                    "--sub-format", "srt",
                    "-o", out_template,
                    "--retries", "2",
                    "--cookies", "/app/assets/yt_cookies/cookies.txt",
                ]

                if captions_type == CaptionType.MANUAL:
                    cmd.extend(["--write-subs", "--sub-langs", lang_code])
                elif captions_type == CaptionType.AUTO:
                    cmd.extend(["--write-auto-subs", "--sub-langs", lang_code])

                cmd.append(url)

                subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                self.logger.info(f"[2차] yt-dlp 실행 명령어: {' '.join(cmd)}")

                pattern = os.path.join(temp_dir, f"{video_id}.{captions_type}.*.srt")
                files = glob.glob(pattern)

                target_file = files[0]
                with open(target_file, "r", encoding="utf-8") as f:
                    return f.read()

            except CaptionException as e:
                return ""

            except Exception as e:
                self.logger.error(f"[2차] 자막 다운로드 중 오류가 발생했습니다. error={e}")
                return ""


    def get_captions_with_lang_code(self, video_id: str) -> Tuple[str, str]:
        # 1) 영상 정보 조회
        video_info = self.__get_video_info_json(video_id)

        # 2) 자막 정보 추출
        download_url, lang_code, captions_type = self.__extract_captions_info(video_info, video_id)

        # 3) url로 자막 다운로드
        raw_captions = self.__download_captions_from_url(download_url)
        if raw_captions:
            self.logger.info(f"[1차] 자막 다운로드 성공: video_id={video_id}")
            return raw_captions, lang_code

        # 4) yt-dlp로 자막 다운로드
        effective_lang = f"{lang_code}-orig" if captions_type == CaptionType.AUTO else lang_code
        raw_captions = self.__download_captions_from_ytdlp(video_id, captions_type, effective_lang)

        if raw_captions:
            self.logger.info(f"[2차] 자막 다운로드 성공: video_id={video_id}")
            return raw_captions, lang_code

        self.logger.error(f"자막 다운로드 실패: video_id={video_id}")
        raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)