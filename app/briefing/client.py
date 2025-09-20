import logging
from typing import List, Optional, Tuple

import requests


class BriefingClient:
    def __init__(self, api_key: str, timeout: float = 20.0):
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.timeout = timeout

    def fetch_page(
        self,
        video_id: str,
        order: str,
        page_token: Optional[str],
        remaining: int,
    ) -> Tuple[List[dict], Optional[str]]:
        """
        YouTube Data API에서 댓글 페이지를 가져옴.
        """
        base_url = "https://www.googleapis.com/youtube/v3/commentThreads"
        params = {
            "part": "snippet",
            "videoId": video_id,
            "key": self.api_key,
            "order": order,
            "maxResults": min(100, max(1, remaining)),
        }
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get(base_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", []), data.get("nextPageToken")

    def extract_comments(
        self,
        video_id: str,
        order: str,
        max_each: int,
        seen_ids: set,
    ) -> List[str]:
        """
        주어진 order(relevance/time)로 댓글을 수집.
        - seen_ids 에 이미 있는 댓글 ID는 건너뜀
        - 최대 max_each 개수까지 수집
        """
        comments: List[str] = []
        ids = set()
        token = None

        while len(ids) < max_each:
            try:
                items, token = self.fetch_page(video_id, order, token, max_each - len(ids))
            except Exception as e:
                self.logger.exception(f"{order} 댓글 페이지 조회 중 오류: {e}")
                break

            if not items:
                break

            for it in items:
                try:
                    top = it["snippet"]["topLevelComment"]
                    cid = top["id"]
                    text = top["snippet"]["textDisplay"]
                except KeyError:
                    continue

                if cid in seen_ids:
                    continue

                seen_ids.add(cid)
                ids.add(cid)
                comments.append(text)

                if len(ids) >= max_each:
                    break

            if not token:
                break

        return comments

    def get_video_comments(self, video_id: str, max_each: int = 50) -> List[str]:
        """
        유튜브 댓글을 인기순/최신순 각각 최대 max_each 개수 가져와 합친 리스트 반환.
        중복은 제거되며, 인기순 우선.
        """
        try:
            seen_ids = set()

            # 인기순 수집
            popular = self.extract_comments(video_id, "relevance", max_each, seen_ids)

            # 최신순 수집 (인기순과 중복 제거)
            recent = self.extract_comments(video_id, "time", max_each, seen_ids)

            merged = popular + recent

            return merged

        except Exception as e:
            self.logger.exception(f"댓글 조회 중 오류가 발생했습니다: {e}")
            return []
