import json
import logging
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.caption.exception import CaptionErrorCode, CaptionException


class CaptionRecipeValidator:
    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        inference_profile_arn: str,
        max_tokens: int = 64,
        temperature: float = 0.0,
    ):
        self.logger = logging.getLogger(__name__)
        self.model_id = model_id
        self.region = region
        self.inference_profile_arn = inference_profile_arn
        self.max_tokens = max_tokens
        self.temperature = temperature

        base = Path(__file__).parent / "prompt"
        self.template = (base / "recipe_detect.md").read_text(encoding="utf-8")
        self.tools = json.loads((base / "emit_bit_tool.json").read_text(encoding="utf-8"))

        self.client = boto3.client(
            "bedrock-runtime",
            config=Config(region_name=region, retries={"max_attempts": 3, "mode": "adaptive"}),
        )

    def __converse(self, user_prompt: str) -> int:
        model_identifier = self.inference_profile_arn or self.model_id

        try:
            resp = self.client.converse(
                modelId=model_identifier,
                messages=[{"role":"user","content":[{"text": user_prompt}]}],
                toolConfig={
                    "tools": self.tools,
                    "toolChoice": {"tool": {"name": "emit_bit"}},
                },
                inferenceConfig={"maxTokens": self.max_tokens, "temperature": self.temperature},
            )

            content = resp.get("output", {}).get("message", {}).get("content", [])

            for item in content:
                tool_use = item.get("toolUse")
                if tool_use and tool_use.get("name").lower() == "emit_bit":
                    obj = tool_use.get("input") or {}
                    return obj.get("bit")

        except ClientError as e:
            self.logger.error(f"Bedrock invoke failed: {e}")
            raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)
        except Exception as e:
            self.logger.error(f"Unexpected error while calling Bedrock: {e}")
            raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)

        return None

    def validate(self, captions: str, lang_code: str, video_id: str):
        try:
            # 1) 프롬프트 채우기
            prompt = (
                self.template.replace("{{ lang_code }}", lang_code)
                             .replace("{{ captions }}", captions)
            )

            # 2) Bedrock 호출
            bit = self.__converse(prompt)

            # 3) 검증
            if bit not in (0, 1):
                self.logger.error(
                    f"자막에서 레시피 여부 검증 중 오류가 발생했습니다: video_id={video_id}, bit={bit}"
                )
                raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)

            if bit != 1:
                self.logger.error(f"자막에서 레시피를 찾을 수 없습니다: video_id={video_id}")
                raise CaptionException(CaptionErrorCode.CAPTION_RECIPE_NOT_FOUND)

        except CaptionException:
            raise
        except Exception as e:
            self.logger.error(
                f"자막에서 레시피 여부 검증 중 예상치 못한 오류가 발생했습니다: video_id={video_id}, error={e}"
            )
            raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)
