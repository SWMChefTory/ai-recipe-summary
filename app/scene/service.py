import asyncio
import json
import logging
from typing import Any, Dict, List

from app.enum import LanguageType
from app.scene.generator import SceneGenerator


class SceneService:
    def __init__(self, generator: SceneGenerator):
        self.logger = logging.getLogger(__name__)
        self.generator = generator

    async def generate_scenes(
        self,
        file_uri: str,
        mime_type: str,
        steps: List[Dict[str, Any]],
        language: LanguageType,
    ) -> List[Dict[str, Any]]:
        scenes: List[Dict[str, Any]] = await asyncio.to_thread(
            self.generator.generate_scenes,
            file_uri,
            mime_type,
            steps,
            language,
        )

        self.logger.info(
            f"{len(scenes)}개의 장면 생성 완료. Preview(Top 3): "
            f"{json.dumps(scenes[:3], ensure_ascii=False)}"
        )

        return scenes
