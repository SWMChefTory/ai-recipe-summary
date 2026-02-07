import asyncio
import json
import logging
from typing import List

from app.enum import LanguageType
from app.step.generator import StepGenerator
from app.step.schema import StepGroup


class StepService:
    def __init__(self, generator: StepGenerator):
        self.logger = logging.getLogger(__name__)
        self.generator = generator

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
