import logging
from typing import List, Optional, Tuple

import requests

from app.briefing.exception import BriefingErrorCode, BriefingException


class BriefingClient:
    def __init__(self, api_key: str, timeout: float = 20.0):
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.timeout = timeout

    def __get_video_comment_count(self, video_id: str) -> int:
        try:
            base_url = "https://www.googleapis.com/youtube/v3/videos"
            params = {
                "part": "statistics",
                "id": video_id,
                "key": self.api_key,
            }
            resp = requests.get(base_url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()

            if not data.get("items") or "statistics" not in data["items"][0]:
                self.logger.warning(f"'{video_id}' 영상의 통계를 찾을 수 없습니다.")
                return 0

            comment_count = int(data["items"][0]["statistics"].get("commentCount", 0))
            return comment_count
        except Exception as e:
            self.logger.exception(f"영상 통계 조회 중 오류가 발생했습니다: {e}")
            return 0

    def __fetch_page(
        self,
        video_id: str,
        order: str,
        page_token: Optional[str],
        remaining: int,
    ) -> Tuple[List[dict], Optional[str]]:
        try:
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

            resp = requests.get(base_url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data.get("items", []), data.get("nextPageToken")
        except Exception as e:
            self.logger.exception(f"댓글 페이지 조회 중 오류가 발생했습니다: {e}")
            raise

    def __extract_comments(
        self,
        video_id: str,
        order: str,
        max_count: int,
        extracted_ids: set,
    ) -> List[str]:
        try:
            comments: List[str] = []
            ids = set()
            token = None

            while len(ids) < max_count:
                items, token = self.__fetch_page(video_id, order, token, max_count - len(ids))

                if not items:
                    break

                for it in items:
                    try:
                        top = it["snippet"]["topLevelComment"]
                        cid = top["id"]
                        text = top["snippet"]["textDisplay"]
                    except KeyError:
                        self.logger.warning(f"댓글 읽기 중 오류가 발생했습니다: {it}")
                        continue

                    if cid in extracted_ids:
                        continue

                    extracted_ids.add(cid)
                    ids.add(cid)
                    comments.append(text)

                    if len(ids) >= max_count:
                        break

                if not token:
                    break

            return comments
        except Exception as e:
            self.logger.exception(f"댓글 추출 중 오류가 발생했습니다: {e}")
            raise
    
    def get_video_comments(self, video_id: str) -> List[str]:
        try:
            total_comments = self.__get_video_comment_count(video_id)
            self.logger.info(f"'{video_id}' 영상의 총 댓글 수: {total_comments}")

            if total_comments <= 10:
                return []

            extracted_ids = set()

            if total_comments < 50:
                return self.__extract_comments(video_id, "time", 50, extracted_ids)

            if 50 <= total_comments <= 1000:
                max_count = 25
            else:
                max_count = 50

            # 인기순 수집
            popular = self.__extract_comments(video_id, "relevance", max_count, extracted_ids)

            # 최신순 수집 (인기순과 중복 제거)
            recent = self.__extract_comments(video_id, "time", max_count, extracted_ids)

            return popular + recent

        except Exception as e:
            self.logger.error(f"댓글 조회 중 오류가 발생했습니다: {e}")
            raise BriefingException(BriefingErrorCode.BRIEFING_GENERATE_FAILED)