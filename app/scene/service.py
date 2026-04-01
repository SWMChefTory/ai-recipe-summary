import asyncio
import json
import logging
from typing import Any, Dict, List
from uuid import UUID

from app.enum import LanguageType
from app.scene.generator import SceneGenerator
from app.scene.schema import SceneOut


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

    @staticmethod
    def _timecode_to_seconds(tc: str) -> float:
        """HH:MM:SS → 초(float) 변환"""
        parts = tc.strip().split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

    @staticmethod
    def assemble(
        raw_scenes: List[Dict[str, Any]],
        step_number_to_id: Dict[int, UUID],
    ) -> List[SceneOut]:
        """Gemini 원시 응답을 백엔드 응답 형식으로 변환.

        - step(int) → step_id(UUID)
        - start/end HH:MM:SS → 초(float)
        - importantScore → important_score
        """
        out: List[SceneOut] = []
        for scene in raw_scenes:
            step_num = scene.get("step")
            step_id = step_number_to_id.get(step_num)
            if step_id is None:
                continue

            out.append(SceneOut(
                step_id=step_id,
                label=scene.get("label", ""),
                start=SceneService._timecode_to_seconds(scene["start"]),
                end=SceneService._timecode_to_seconds(scene["end"]),
                important_score=scene.get("importantScore", 5),
            ))
        return out
