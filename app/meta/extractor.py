import json
import logging
from pathlib import Path
from typing import List

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.meta.exception import MetaErrorCode, MetaException
from app.meta.schema import Ingredient, MetaResponse


class MetaExtractor:
    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        inference_profile_arn: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        extract_prompt_path: Path,
        extract_tool_path: Path,        
        extract_ingredient_prompt_path: Path,
        extract_ingredient_tool_path: Path,
    ):
        self.logger = logging.getLogger(__name__)
        self.model_id = model_id
        self.region = region
        self.inference_profile_arn = inference_profile_arn
        self.max_tokens = max_tokens
        self.temperature = temperature

        self.extract_prompt = extract_prompt_path.read_text(encoding="utf-8")
        self.extract_tool = json.loads(extract_tool_path.read_text(encoding="utf-8"))

        self.extract_ingredient_prompt = extract_ingredient_prompt_path.read_text(encoding="utf-8")
        self.extract_ingredient_tool = json.loads(extract_ingredient_tool_path.read_text(encoding="utf-8"))

        self.client = boto3.client(
            "bedrock-runtime",
            config=Config(region_name=region, retries={"max_attempts": 3, "mode": "adaptive"})
        )

    @staticmethod
    def __safe_int(value, default: int = 0) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    # --------- 설명+댓글에서 재료만 뽑는 LLM 호출 ---------
    def __converse_ingredients_from_description(self, user_prompt: str) -> List[Ingredient]:
        model_identifier = self.inference_profile_arn or self.model_id
        try:
            resp = self.client.converse(
                modelId=model_identifier,
                system=[{"text": """
                    You must call the provided tool only. Do not output any free-form text.

                    All natural-language content in the tool arguments must be written in Korean only.
                    Avoid using English entirely. 
                    Fields such as description, ingredients.name, and tags must all be natural Korean expressions.
                """}],
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                toolConfig={
                    "tools": self.extract_ingredient_tool,
                    "toolChoice": {"tool": {"name": "emit_ingredients"}}
                },
                inferenceConfig={"maxTokens": self.max_tokens, "temperature": self.temperature},
            )

            content = resp.get("output", {}).get("message", {}).get("content", [])
            for item in content:
                tool_use = item.get("toolUse")
                if tool_use and tool_use.get("name", "").lower() == "emit_ingredients":
                    obj = tool_use.get("input") or {}
                    arr = obj.get("ingredients") or []
                    out: List[Ingredient] = []
                    for ing in arr:
                        raw_name = ing.get("name") or ""
                        name = raw_name.strip()

                        raw_amount = ing.get("amount")
                        amount = self.__safe_int(raw_amount, 0)

                        unit = ing.get("unit") or ""

                        if name:
                            out.append(Ingredient(name=name, amount=amount, unit=unit))
                    return out

            # 툴 호출이 안 나왔으면 빈 리스트
            return []
        except ClientError as e:
            self.logger.error(f'{e}')
            raise MetaException(MetaErrorCode.META_BEDROCK_INVOKE_FAILED)
        except Exception as e:
            self.logger.error(f'{e}')
            raise MetaException(MetaErrorCode.META_INGREDIENTS_EXTRACT_FAILED)

    def extract_ingredients_from_description(
        self,
        description: str,
        channel_owner_top_level_comments: List[str]
    ) -> List[Ingredient]:
        prompt = self.extract_ingredient_prompt.replace("{{ description }}", description)
        prompt = prompt.replace(
            "{{ channel_owner_top_level_comments }}",
            "\n".join(channel_owner_top_level_comments),
        )
        try:
            return self.__converse_ingredients_from_description(prompt)
        except MetaException:
            return []

    # --------- 전체 메타 정보 추출 LLM 호출 ---------
    def __converse(self, user_prompt: str) -> MetaResponse:
        model_identifier = self.inference_profile_arn or self.model_id
        try:
            resp = self.client.converse(
                modelId=model_identifier,
                system=[{"text": """
                    You must call the provided tool only. Do not output any free-form text.

                    All natural-language content in the tool arguments must be written in Korean only.
                    Avoid using English entirely. 
                    Fields such as description, ingredients.name, and tags must all be natural Korean expressions.
                """}],
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                toolConfig={
                    "tools": self.extract_tool,
                    "toolChoice": {"tool": {"name": "emit_meta"}}
                },
                inferenceConfig={"maxTokens": self.max_tokens, "temperature": self.temperature},
            )

            content = resp.get("output", {}).get("message", {}).get("content", [])
            for item in content:
                tool_use = item.get("toolUse")
                if tool_use and tool_use.get("name", "").lower() == "emit_meta":
                    meta = tool_use.get("input") or {}

                    raw_description = meta.get("description") or ""
                    description = raw_description.strip()

                    raw_ingredients = meta.get("ingredients") or []
                    ingredients = []
                    for ing in raw_ingredients:
                        name = (ing.get("name") or "").strip()
                        amount = self.__safe_int(ing.get("amount"), 0)
                        unit = ing.get("unit") or ""
                        if name:
                            ingredients.append(
                                {"name": name, "amount": amount, "unit": unit}
                            )

                    raw_tags = meta.get("tags") or []
                    tags = [t for t in raw_tags if t]

                    servings = self.__safe_int(meta.get("servings"), 2)
                    cook_time = self.__safe_int(meta.get("cook_time"), 30)

                    return MetaResponse(
                        description=description,
                        ingredients=ingredients,
                        tags=tags,
                        servings=servings,
                        cook_time=cook_time,
                    )

            # 툴 호출이 없으면 실패로 처리
            raise MetaException(MetaErrorCode.META_EXTRACT_FAILED)

        except ClientError as e:
            self.logger.error(f'{e}')
            raise MetaException(MetaErrorCode.META_BEDROCK_INVOKE_FAILED)
        except MetaException:
            raise
        except Exception as e:
            self.logger.error(f'{e}')
            raise MetaException(MetaErrorCode.META_EXTRACT_FAILED)

    def extract(self, captions: str) -> MetaResponse:
        prompt = self.extract_prompt.replace("{{ captions }}", captions)
        return self.__converse(prompt)
