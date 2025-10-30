import html
import logging
from typing import List

import requests


class MetaClient:
    def __init__(self, api_key: str, timeout: float = 20.0):
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.timeout = timeout

    def get_video_description(self, video_id: str) -> str:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet",
            "id": video_id,
            "key": self.api_key
        }
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data["items"][0]["snippet"]["description"]
            
        except Exception as e:
            self.logger.exception(f"동영상 설명란 조회 중 오류 발생: {e}")
            return ""

    def __get_channel_id(self, video_id: str) -> str | None:
        try:
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "snippet", "id": video_id, "key": self.api_key},
                timeout=self.timeout,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            return items[0]["snippet"]["channelId"] if items else None
        except Exception as e:
            self.logger.exception(f"channelId 조회 중 오류: {e}")
            return None

    def get_channel_owner_top_level_comments(
        self,
        video_id: str,
        order: str = "relevance",
        scan_pages: int = 6,
    ) -> List[str]:
        ch_id = self.__get_channel_id(video_id)
        if not ch_id:
            return []

        url = "https://www.googleapis.com/youtube/v3/commentThreads"
        params = {
            "part": "snippet",
            "videoId": video_id,
            "textFormat": "plainText",
            "maxResults": 100,
            "order": order,
            "key": self.api_key,
        }

        comments: List[str] = []
        seen_ids: set[str] = set()
        page_token = None

        try:
            for _ in range(max(1, scan_pages)):
                if page_token:
                    params["pageToken"] = page_token
                resp = requests.get(url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("items", []):
                    top = item["snippet"]["topLevelComment"]
                    sn = top["snippet"]
                    author_ch = (sn.get("authorChannelId") or {}).get("value")
                    if author_ch == ch_id:
                        cid = top["id"]
                        if cid in seen_ids:
                            continue
                        seen_ids.add(cid)
                        text = html.unescape((sn.get("textDisplay") or sn.get("textOriginal") or "").strip())
                        if text:
                            comments.append(text)

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

        except Exception as e:
            self.logger.exception(f"채널 주인 댓글 수집 중 오류: {e}")
            return []

        return comments