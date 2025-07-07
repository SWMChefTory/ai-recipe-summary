"""자막 처리 서비스"""

from __future__ import annotations

import logging
from typing import Dict, List

from app.constants import CaptionConfig


class CaptionService:
    """자막 정규화 처리 서비스"""

    def __init__(self, precision: int = CaptionConfig.DEFAULT_PRECISION) -> None:
        self.precision = precision
        self.logger = logging.getLogger(__name__)
        

    def normalize_captions(self, raw_captions: List[Dict]) -> List[Dict]:
        """원본 자막 데이터를 정규화합니다 (start, end, text 형식)."""
        if not raw_captions:
            return []
            
        normalized_captions = []
        
        for caption_index, caption_segment in enumerate(raw_captions):
            try:
                start_time = self._convert_to_seconds(caption_segment.get("start", 0))
                end_time = self._calculate_end_time(
                    caption_segment, caption_index, raw_captions, start_time
                )
                
                normalized_start = round(start_time, self.precision)
                normalized_end = round(end_time, self.precision)
                
                # 시작과 끝 시간이 같으면 최소 0.1초 간격 보장
                if normalized_end <= normalized_start:
                    normalized_end = normalized_start + 0.1
                
                normalized_caption = {
                    "start": normalized_start,
                    "end": normalized_end,
                    "text": caption_segment.get("text", "")
                }
                normalized_captions.append(normalized_caption)
                
            except Exception as processing_error:
                self.logger.warning(
                    f"자막 세그먼트 정규화 실패: {processing_error}, 데이터: {caption_segment}"
                )
                continue
                
        # 시작 시간순으로 정렬
        normalized_captions.sort(key=lambda caption: caption["start"])
        return normalized_captions

    def _calculate_end_time(
        self, 
        caption_segment: Dict, 
        current_index: int, 
        all_captions: List[Dict], 
        start_time: float
    ) -> float:
        """자막 세그먼트의 종료 시간을 계산합니다."""
        # end 시간이 명시되어 있는 경우
        if ("end" in caption_segment and 
            caption_segment["end"] is not None and 
            caption_segment["end"] != 0):
            return self._convert_to_seconds(caption_segment["end"])
        
        # duration이 명시되어 있는 경우
        if ("duration" in caption_segment and 
            caption_segment["duration"] is not None and 
            caption_segment["duration"] != 0):
            duration = self._convert_to_seconds(caption_segment["duration"])
            return start_time + duration
        
        # 다음 자막의 시작 시간을 사용
        if current_index + 1 < len(all_captions):
            next_caption = all_captions[current_index + 1]
            next_start_time = self._convert_to_seconds(next_caption.get("start", start_time + 3))
            return next_start_time
        
        # 마지막 자막인 경우 기본 3초 추가
        return start_time + 3.0

    def _convert_to_seconds(self, time_value: float | str | None) -> float:
        """시간 값을 초 단위로 변환합니다."""
        if time_value is None:
            return 0.0
        return float(time_value) 