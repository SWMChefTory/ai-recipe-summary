import asyncio
import json
import logging
from typing import List

from app.caption.schema import Caption
from app.step.exception import StepErrorCode, StepException
from app.step.generator import StepGenerator
from app.step.schema import StepGroup


class StepService:
    def __init__(self, generator: StepGenerator, max_concurrency: int = 6):
        self.logger = logging.getLogger(__name__)
        self.generator = generator
        self.semaphore = asyncio.Semaphore(max_concurrency)

    def chunk_captions_by_lines(
        self,
        captions: List[Caption],
        chunk_size: int = 100,
        overlap: int = 15,
    ) -> List[List[Caption]]:
        chunks: List[List[Caption]] = []
        n = len(captions)
        for start_idx in range(0, n, chunk_size):
            end_idx = min(start_idx + chunk_size, n)
            chunk_start = max(0, start_idx - overlap)
            chunk_end = min(n, end_idx + overlap)
            chunks.append(captions[chunk_start:chunk_end])
        return chunks

    async def _run_chunk(self, chunk_json: str) -> List[StepGroup]:
        async with self.semaphore:
            return await asyncio.to_thread(self.generator.summarize, chunk_json)

    async def generate(self, captions: List[Caption]) -> List[StepGroup]:
        # 1) 분할
        chunks = self.chunk_captions_by_lines(captions, 100, 15)
        if not chunks:
            raise StepException(StepErrorCode.CHUNK_NOT_FOUND)

        # 2) 청크별 JSON
        chunk_jsons = [
            json.dumps([seg.model_dump() for seg in ch], ensure_ascii=False)
            for ch in chunks
        ]

        # 3) 병렬 chunk 요약
        per_chunk_steps: List[List[StepGroup]] = await asyncio.gather(
            *[self._run_chunk(cj) for cj in chunk_jsons]
        )

        # 4) 평탄화
        flat_steps: List[StepGroup] = [step for steps in per_chunk_steps for step in steps]

        # 5) JSON 변환 (병합 LLM 입력용)
        flat_steps_json = json.dumps([s.model_dump() for s in flat_steps], ensure_ascii=False)

        # 6) LLM 병합 호출 → List[StepGroup] 반환
        merged_steps: List[StepGroup] = await asyncio.to_thread(
            self.generator.merge,
            flat_steps_json,
        )

        return merged_steps