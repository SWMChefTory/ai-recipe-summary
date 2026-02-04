import asyncio
import json
import logging
from typing import List

from app.caption.schema import Caption
from app.enum import LanguageType
from app.step.exception import StepErrorCode, StepException
from app.step.generator import StepGenerator
from app.step.schema import StepGroup


class StepService:
    DEFAULT_CHUNK_SIZE = 150
    DEFAULT_OVERLAP = 15

    def __init__(self, generator: StepGenerator, max_concurrency: int = 2):
        self.logger = logging.getLogger(__name__)
        self.generator = generator
        self.semaphore = asyncio.Semaphore(max_concurrency)

    def chunk_captions_by_lines(
        self,
        captions: List[Caption],
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ) -> List[List[Caption]]:
        chunks: List[List[Caption]] = []
        n = len(captions)

        for start_idx in range(0, n, chunk_size):
            end_idx = min(start_idx + chunk_size, n)
            chunk_start = max(0, start_idx - overlap)
            chunk_end = min(n, end_idx + overlap)
            chunks.append(captions[chunk_start:chunk_end])

        return chunks


    def _captions_to_json(self, chunk: List[Caption]) -> str:
        return json.dumps([c.model_dump() for c in chunk], ensure_ascii=False)


    def _steps_to_json(self, steps: List[StepGroup]) -> str:
        return json.dumps([s.model_dump() for s in steps], ensure_ascii=False)


    async def _summarize_chunk(self, chunk_json: str, language: LanguageType) -> List[StepGroup]:
        async with self.semaphore:
            return await asyncio.to_thread(self.generator.summarize, chunk_json, language)


    async def generate(self, captions: List[Caption], language: LanguageType) -> List[StepGroup]:
        chunks = self.chunk_captions_by_lines(captions)
        if not chunks:
            raise StepException(StepErrorCode.CHUNK_NOT_FOUND)

        chunk_jsons = [self._captions_to_json(chunk) for chunk in chunks]

        per_chunk_steps: List[List[StepGroup]] = await asyncio.gather(
            *(self._summarize_chunk(chunk_json, language) for chunk_json in chunk_jsons)
        )

        flat_steps: List[StepGroup] = [step for steps in per_chunk_steps for step in steps]
        flat_steps_json = self._steps_to_json(flat_steps)

        merged_steps: List[StepGroup] = await asyncio.to_thread(
            self.generator.merge,
            flat_steps_json,
            language,
        )

        preview_steps = [s.model_dump() for s in merged_steps[:3]]
        
        self.logger.info(f"{len(merged_steps)}개의 스텝 생성 완료. Preview(Top 3): {json.dumps(preview_steps, ensure_ascii=False)}")

        return merged_steps

    async def generate_by_video(self, file_uri: str, mime_type: str, language: LanguageType) -> List[StepGroup]:
        steps: List[StepGroup] = await asyncio.to_thread(
            self.generator.summarize_video,
            file_uri,
            mime_type,
            language,
        )

        preview_steps = [s.model_dump() for s in steps[:3]]
        self.logger.info(f"{len(steps)}개의 스텝 생성 완료 (Video). Preview(Top 3): {json.dumps(preview_steps, ensure_ascii=False)}")

        return steps
