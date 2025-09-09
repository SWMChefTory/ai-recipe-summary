import logging

import requests


class MetaClient:
    def __init__(self, api_key: str, timeout: float = 20.0):
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.timeout = timeout

    def get_video_description(self, video_id: str) -> str:
        params = {
            "part": "snippet",
            "id": video_id,
            "key": self.api_key,
        }
        try:
            resp = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data["items"][0]["snippet"]["description"]
            
        except Exception as e:
            self.logger.exception(f"동영상 설명란 조회 중 오류 발생: {e}")
            return ""