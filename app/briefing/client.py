import logging
from typing import List, Optional, Tuple

import requests

from app.briefing.exception import BriefingErrorCode, BriefingException


class BriefingClient:
    def __init__(self, api_key: str, timeout: float = 20.0):
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.timeout = timeout

    def __fetch_page(
        self,
        video_id: str,
        page_token: Optional[str],
        remaining: int,
    ) -> Tuple[List[dict], Optional[str]]:
        try:
            base_url = "https://www.googleapis.com/youtube/v3/commentThreads"
            
            request_count = min(100, max(1, remaining))

            params = {
                "part": "snippet",
                "videoId": video_id,
                "key": self.api_key,
                "order": "time",  # 최신순
                "maxResults": request_count,
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

    def get_video_comments(self, video_id: str) -> List[str]:
        try:
            comments: List[str] = []
            token = None
            max_limit = 500  # 최대 수집 한도 설정
            
            self.logger.info(f"'{video_id}' 영상의 댓글 수집을 시작합니다. (최대 {max_limit}개, 최신순)")

            while len(comments) < max_limit:
                # 앞으로 더 가져와야 할 개수 계산
                remaining = max_limit - len(comments)
                
                # API 호출
                items, token = self.__fetch_page(video_id, token, remaining)

                if not items:
                    break

                for it in items:
                    try:
                        # 대댓글(replies)은 무시하고, 최상위 댓글(topLevelComment)만 추출
                        top = it["snippet"]["topLevelComment"]
                        text = top["snippet"]["textDisplay"]
                        comments.append(text)
                    except KeyError:
                        self.logger.warning(f"댓글 데이터 파싱 실패: {it}")
                        continue
                    
                    # 루프 도중 1,000개가 채워지면 즉시 중단
                    if len(comments) >= max_limit:
                        break

                # 다음 페이지가 없거나, 목표치를 다 채웠으면 종료
                if not token or len(comments) >= max_limit:
                    break
            
            self.logger.info(f"수집 완료: 총 {len(comments)}개의 댓글을 가져왔습니다.")
            return comments

        except Exception as e:
            self.logger.error(f"댓글 조회 중 오류가 발생했습니다: {e}")
            raise BriefingException(BriefingErrorCode.BRIEFING_GENERATE_FAILED)