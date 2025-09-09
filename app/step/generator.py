import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.step.exception import StepErrorCode, StepException
from app.step.schema import StepGroup


class StepGenerator:
    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        inference_profile_arn: str,
        max_tokens: int = 16000,
        temperature: float = 0.0,
        step_tool_path: Path,
        summarize_user_prompt_path: Path,
        merge_user_prompt_path: Path,
    ):
        self.logger = logging.getLogger(__name__)
        self.model_id = model_id
        self.region = region
        self.inference_profile_arn = inference_profile_arn
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.summarize_user_prompt = summarize_user_prompt_path.read_text(encoding="utf-8")
        self.merge_user_prompt = merge_user_prompt_path.read_text(encoding="utf-8")
        self.step_tool = json.loads(step_tool_path.read_text(encoding="utf-8"))

        self.client = boto3.client(
            "bedrock-runtime",
            config=Config(region_name=region, retries={"max_attempts": 3, "mode": "adaptive"})
        )


    def _call_converse_for_steps(self, user_prompt: str) -> List[StepGroup]:
        """공통 호출: 단일 툴 emit_steps 사용"""
        model_identifier = self.inference_profile_arn or self.model_id
        try:
            resp = self.client.converse(
                modelId=model_identifier,
                system=[{"text": "You must call the provided tool only. Do not produce free-form text. All natural-language must be Korean."}],
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                toolConfig={"tools": self.step_tool, "toolChoice": {"tool": {"name": "emit_steps"}}},
                inferenceConfig={"maxTokens": self.max_tokens, "temperature": self.temperature},
            )
            content = resp["output"]["message"]["content"]
            for item in content:
                tu = item.get("toolUse")
                if tu and tu.get("name") == "emit_steps":
                    raw_steps = (tu.get("input") or {}).get("steps", []) or []
                    return [StepGroup(**s) for s in raw_steps]
        except ClientError as e:
            self.logger.error("Bedrock converse failed: %s", e, exc_info=True)
            return []
        except Exception:
            self.logger.exception("Unexpected converse response")
            return []
        return []


    def summarize(self, captions_json_str: str) -> List[StepGroup]:
        user_prompt = self.summarize_user_prompt.replace("{{ captions }}", captions_json_str)
        return self._call_converse_for_steps(user_prompt)


    def merge(self, flat_steps_json_str: str) -> List[StepGroup]:
        user_prompt = self.merge_user_prompt.replace("{{ steps }}", flat_steps_json_str)
        result = self._call_converse_for_steps(user_prompt)
        if not result:
            raise StepException(StepErrorCode.STEP_GENERATE_FAILED)
        return result