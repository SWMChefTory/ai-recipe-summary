import json
import logging
from pathlib import Path
from typing import List, Optional

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


    def __converse_ingredients_from_description(self, user_prompt: str) -> List[Ingredient]:
        model_identifier = self.inference_profile_arn or self.model_id
        try:
            resp = self.client.converse(
                modelId=model_identifier,
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                toolConfig={
                    "tools": self.extract_ingredient_tool,
                    "toolChoice": {"tool": {"name": "emit_ingredients"}}
                },
                inferenceConfig={"maxTokens": self.max_tokens, "temperature": self.temperature},
            )

            content = resp.get("output").get("message").get("content")
            for item in content:
                tool_use = item.get("toolUse")
                if tool_use and tool_use.get("name").lower() == "emit_ingredients":
                    obj = tool_use.get("input")
                    arr = obj.get("ingredients")
                    out = []
                    for ing in arr:
                        name = ing.get("name").strip()
                        amount = float(ing.get("amount"))
                        unit = ing.get("unit")
                        if name:
                            out.append(Ingredient(name=name, amount=amount, unit=unit))
                    return out
        except ClientError as e:
            self.logger.error(f'{e}')
            raise MetaException(MetaErrorCode.META_BEDROCK_INVOKE_FAILED)
        except Exception as e:
            self.logger.error(f'{e}')
            raise MetaException(MetaErrorCode.META_INGREDIENTS_EXTRACT_FAILED)

    def extract_ingredients_from_description(self, description: str) -> List[Ingredient]:
        """유튜브 설명란에서 재료를 추출"""
        prompt = self.extract_ingredient_prompt.replace("{{ description }}", description)
        try:
            return self.__converse_ingredients_from_description(prompt)
        except MetaException:
            return []


    def __converse(self, user_prompt: str) -> MetaResponse:
        """Bedrock API"""
        model_identifier = self.inference_profile_arn or self.model_id
        try:
            resp = self.client.converse(
                modelId=model_identifier,
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
                if tool_use and tool_use.get("name").lower() == "emit_meta":
                    meta = tool_use.get("input")

                    description = meta.get("description").strip()
                    ingredients = meta.get("ingredients")
                    for ingredient in ingredients:  
                        ingredient["amount"] = float(ingredient["amount"])
                    tags = meta.get("tags")
                    servings = int(meta.get("servings"))  
                    cook_time = int(meta.get("cook_time"))

                    return MetaResponse(
                        description=description,
                        ingredients=ingredients,
                        tags=tags,
                        servings=servings,
                        cook_time=cook_time,
                    )

        except ClientError as e:
            self.logger.error(f'{e}')
            raise MetaException(MetaErrorCode.META_BEDROCK_INVOKE_FAILED)
        except Exception as e:
            self.logger.error(f'{e}')
            raise MetaException(MetaErrorCode.META_EXTRACT_FAILED)
        

    def extract(self, captions: str) -> MetaResponse:
        """자막에서 메타데이터 추출"""
        prompt = self.extract_prompt.replace("{{ captions }}", captions)
        return self.__converse(prompt)