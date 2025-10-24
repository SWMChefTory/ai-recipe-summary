import asyncio
import glob
import json
import logging
import os
import random
import subprocess
import tempfile
from typing import List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from app.caption.enum import CaptionType
from app.caption.exception import CaptionErrorCode, CaptionException


class CaptionClient:
    def __init__(
        self,
        region: str,
        aws_lambda_function_urls: List[str],
        aws_access_key_id: str,
        aws_secret_access_key: str,
    ):
        self.logger = logging.getLogger(__name__)
        self.region = region
        self.aws_lambda_function_urls = aws_lambda_function_urls
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

    def __get_video_info_json(self, video_id: str) -> dict:
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            cmd = [
                "yt-dlp",
                "-J",
                "--skip-download",
                "--force-ipv4",
                "--retries", "2",
                "--cookies", "/app/assets/yt_cookies/cookies.txt",
                url,
            ]
            self.logger.info(f"[Step 0] yt-dlp 실행 명령어: {' '.join(cmd)}")
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if res.returncode != 0:
                self.logger.error(f"[Step 0] yt-dlp 실행 중 오류가 발생했습니다. error={res.stderr}")
                raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)

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
            self.logger.error(f"[Step 1] 자막 다운로드 중 오류가 발생했습니다. error={e}")
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
                    "--write-subs",
                    "-o", out_template,
                    "--force-ipv4",
                    "--retries", "2",
                    "--cookies", "/app/assets/yt_cookies/cookies.txt",
                ]

                if captions_type == CaptionType.MANUAL:
                    cmd.extend(["--write-subs", "--sub-langs", lang_code])
                elif captions_type == CaptionType.AUTO:
                    cmd.extend(["--write-auto-subs", "--sub-langs", lang_code])

                cmd.append(url)

                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                self.logger.info(f"[Step 2] yt-dlp 실행 명령어: {' '.join(cmd)}")

                if proc.returncode != 0:
                    self.logger.error(f"[Step 2] yt-dlp 실행 중 오류가 발생했습니다. error={proc.stderr}")
                    return ""

                pattern = os.path.join(temp_dir, f"{video_id}.{captions_type}.*.srt")
                files = glob.glob(pattern)

                if not files:
                    self.logger.error(f"[Step 2] 자막 파일이 존재하지 않습니다. pattern={pattern}")
                    return ""

                target_file = files[0]
                with open(target_file, "r", encoding="utf-8") as f:
                    return f.read()


            except subprocess.TimeoutExpired as e:
                self.logger.error(f"[Step 2] yt-dlp 실행 중 시간 초과가 발생했습니다. error={e}")
                return ""

            except UnicodeDecodeError as e:
                self.logger.error(f"[Step 2] UTF-8 디코딩 중 오류가 발생했습니다. error={e}")
                return ""

            except CaptionException as e:
                return ""
            
            except Exception as e:
                self.logger.error(f"[Step 2] 자막 다운로드 중 오류가 발생했습니다. error={e}")
                return ""

    async def fetch_captions_from_lambda(self, video_id: str):
        """Lambda Function URL (AWS_IAM 인증) 호출"""
        def call():
            # 1) payload는 문자열로 "한 번만" 직렬화 (서명=전송 동일)
            payload_json = json.dumps({"video_id": video_id}, separators=(",", ":"))

            # 2) URL 랜덤 선택
            url = random.choice(self.aws_lambda_function_urls)

            # 3) URL에서 region 파싱 (ex: id.lambda-url.ap-northeast-1.on.aws)
            host = urlparse(url).netloc
            # host 분해: '<id>.lambda-url.<region>.on.aws'
            region_from_url = host.split(".lambda-url.")[1].split(".on.aws")[0]

            # 4) 자격증명
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region,  # 세션 리전은 아무거나 OK
            )
            creds = session.get_credentials().get_frozen_credentials()

            # 5) 같은 바디로 서명 + 같은 바디로 전송
            req = AWSRequest(
                method="POST",
                url=url,
                data=payload_json,
                headers={"Content-Type": "application/json"},
            )
            SigV4Auth(creds, "lambda", region_from_url).add_auth(req)

            self.logger.info(f"Lambda region: {region_from_url}")

            res = requests.post(url, data=payload_json, headers=dict(req.headers), timeout=90)
            res.raise_for_status()
            data = res.json()

            # Lambda proxy 형식
            if isinstance(data, dict) and "body" in data:
                body = data["body"]
                if isinstance(body, str):
                    try:
                        body = json.loads(body)
                    except Exception:
                        pass
                return body["captions"], body["lang_code"]
    
            # Function URL 직반환 형식
            if isinstance(data, dict) and "captions" in data and "lang_code" in data:
                return data["captions"], data["lang_code"]
    
            self.logger.error(f"Unexpected Lambda response: {data}")
            raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)

        return await asyncio.to_thread(call)

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
            self.logger.info(f"[Step 2] 자막 다운로드 성공: video_id={video_id}")
            return raw_captions, lang_code

        self.logger.error(f"자막 다운로드 실패: video_id={video_id}")
        raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)