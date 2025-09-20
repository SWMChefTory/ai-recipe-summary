import json
import logging
from pathlib import Path
from typing import List

import boto3
from botocore.config import Config

from app.briefing.exception import BriefingErrorCode, BriefingException


class BriefingGenerator:
    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        inference_profile_arn: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        generate_user_prompt_path: Path,
        briefing_tool_path: Path,
    ):
        self.logger = logging.getLogger(__name__)
        self.model_id = model_id
        self.region = region
        self.inference_profile_arn = inference_profile_arn
        self.max_tokens = max_tokens
        self.temperature = temperature

        # ---- 프롬프트/툴 로드 ----
        self.briefing_prompt = generate_user_prompt_path.read_text(encoding="utf-8")
        self.briefing_tool = json.loads(briefing_tool_path.read_text(encoding="utf-8"))

        self.client = boto3.client(
            "bedrock-runtime",
            config=Config(region_name=region, retries={"max_attempts": 3, "mode": "adaptive"})
        )

    def _converse_briefing(self, user_prompt: str) -> List[str]:
        """
        LLM 결과(브리핑 문장 리스트)를 반환.
        - toolUse name="emit_briefing", input={"items": ["문장1", "문장2", ...]} 형태를 기대.
        """
        try:
            model_identifier = self.inference_profile_arn or self.model_id
        
            resp = self.client.converse(
                modelId=model_identifier,
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                toolConfig={
                    "tools": self.briefing_tool,
                    "toolChoice": {"tool": {"name": "emit_briefing"}}
                },
                inferenceConfig={
                    "maxTokens": self.max_tokens,
                    "temperature": self.temperature
                },
            )
            content = resp.get("output", {}).get("message", {}).get("content", [])

            for item in content:
                tu = item.get("toolUse")
                if tu and tu.get("name") == "emit_briefing":
                    obj = tu.get("input", {})
                    items = obj.get("items", [])
                    return [str(item) for item in items]

        except Exception as e:
            self.logger.error(f"브리핑 생성 중 오류가 발생했습니다: {e}")
            raise BriefingException(BriefingErrorCode.BRIEFING_GENERATE_FAILED)

    def generate_briefing_from_comments(self, comments: List[str]) -> List[str]:
        """
        댓글(List[str])을 입력받아 브리핑 문장 리스트를 반환.
        - 레시피 관련 2~5문장
        - 2개 미만이면 예외 발생
        """
        try:
            comments_json = json.dumps(
                [c for c in comments if isinstance(c, str) and c.strip()],
                ensure_ascii=False
            )
            prompt = self.briefing_prompt.replace("{{ comments_json }}", comments_json)

            result = self._converse_briefing(prompt)

            # 최대 5개로 제한
            if len(result) > 5:
                result = result[:5]

            # 2개 미만이면 예외 발생
            if len(result) < 2:
                raise BriefingException(BriefingErrorCode.BRIEFING_NOT_ENOUGH_COMMENTS)

            return result

        except Exception as e:
            self.logger.error(f'브리핑 생성 중 오류가 발생했습니다: {e}')
            raise BriefingException(BriefingErrorCode.BRIEFING_GENERATE_FAILED)
