import json
import logging
from pathlib import Path
from typing import List

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.meta.exception import MetaErrorCode, MetaException
from app.meta.schema import Ingredient, MetaResponse


class MetaExtractor:
    def __init__(
        self,
        *,
        client: genai.Client,
        model: str,
        extract_prompt_path: Path,
        extract_tool_path: Path,
        extract_ingredient_prompt_path: Path,
        extract_ingredient_tool_path: Path,
    ):
        self.logger = logging.getLogger(__name__)

        self.client = client
        self.model = model

        # ----- 프롬프트 / 툴 스펙 로드 -----
        self.extract_prompt = extract_prompt_path.read_text(encoding="utf-8")
        self.extract_tool = json.loads(extract_tool_path.read_text(encoding="utf-8"))

        self.extract_ingredient_prompt = extract_ingredient_prompt_path.read_text(encoding="utf-8")
        self.extract_ingredient_tool = json.loads(
            extract_ingredient_tool_path.read_text(encoding="utf-8")
        )

        self.system_instruction = """
            You must call the provided function only. Do not output any free-form text.

            All natural-language content in the function arguments must be written in Korean only.
            Avoid using English entirely.
            Fields such as description, ingredients.name, and tags must all be natural Korean expressions.
            """.strip()

        def _build_tool_from_spec(tool_list: list) -> types.Tool:
            if not tool_list:
                raise ValueError("Tool spec list is empty")

            tool_spec = tool_list[0].get("toolSpec") or {}
            name = tool_spec.get("name")
            description = tool_spec.get("description", "")
            json_schema = (tool_spec.get("inputSchema") or {}).get("json") or {}

            if not name:
                raise ValueError("toolSpec.name is required in tool spec JSON")

            fn_decl = {
                "name": name,
                "description": description,
                "parameters": json_schema,
            }

            return types.Tool(function_declarations=[fn_decl])

        self.ingredients_tool = _build_tool_from_spec(self.extract_ingredient_tool)
        self.meta_tool = _build_tool_from_spec(self.extract_tool)

        self.ingredients_conf = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.0,
            tools=[self.ingredients_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=["emit_ingredients"],
                )
            ),
        )

        self.meta_conf = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.0,
            tools=[self.meta_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=["emit_meta"],
                )
            ),
        )


    @staticmethod
    def __safe_float(value, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def __safe_int(value, default: int = 0) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


    def __converse_ingredients_from_description(self, user_prompt: str) -> List[Ingredient]:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=self.ingredients_conf,
            )

            # 1) python-genai의 편의 속성 먼저 시도
            calls = getattr(response, "function_calls", None) or []

            # 2) fallback: candidates[*].content.parts[*].function_call 에서 수동 파싱 
            if not calls and getattr(response, "candidates", None):
                calls = []
                for cand in response.candidates:
                    content = getattr(cand, "content", None)
                    if not content:
                        continue
                    for part in content.parts:
                        fc = getattr(part, "function_call", None)
                        if fc:
                            calls.append(fc)

            if not calls:
                # 함수 호출이 없으면 "빈 리스트"로 처리 (기존 로직과 동일)
                return []

            for call in calls:
                if call.name != "emit_ingredients":
                    continue

                args = call.args or {}
                arr = args.get("ingredients") or []
                out: List[Ingredient] = []

                for ing in arr:
                    raw_name = ing.get("name") or ""
                    name = raw_name.strip()

                    raw_amount = ing.get("amount")
                    amount = self.__safe_float(raw_amount, 0.0)

                    unit = ing.get("unit") or ""

                    if name:
                        out.append(Ingredient(name=name, amount=amount, unit=unit))

                return out

            return []

        except genai_errors.ClientError as e:
            self.logger.error(f"Gemini API invoke failed (ingredients): {e}")
            raise MetaException(MetaErrorCode.META_BEDROCK_INVOKE_FAILED)
        except Exception as e:
            self.logger.error(f"Ingredient extraction failed: {e}")
            raise MetaException(MetaErrorCode.META_INGREDIENTS_EXTRACT_FAILED)

    def extract_ingredients_from_description(
        self,
        description: str,
        channel_owner_top_level_comments: List[str],
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

    def __converse(self, user_prompt: str) -> MetaResponse:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=self.meta_conf,
            )

            calls = getattr(response, "function_calls", None) or []

            if not calls and getattr(response, "candidates", None):
                calls = []
                for cand in response.candidates:
                    content = getattr(cand, "content", None)
                    if not content:
                        continue
                    for part in content.parts:
                        fc = getattr(part, "function_call", None)
                        if fc:
                            calls.append(fc)

            if not calls:
                raise MetaException(MetaErrorCode.META_EXTRACT_FAILED)

            meta_args = None
            for call in calls:
                if call.name == "emit_meta":
                    meta_args = call.args or {}
                    break

            if meta_args is None:
                raise MetaException(MetaErrorCode.META_EXTRACT_FAILED)

            raw_description = meta_args.get("description") or ""
            description = raw_description.strip()

            raw_ingredients = meta_args.get("ingredients") or []
            ingredients = []
            for ing in raw_ingredients:
                name = (ing.get("name") or "").strip()
                amount = self.__safe_float(ing.get("amount"), 0.0)
                unit = ing.get("unit") or ""
                if name:
                    ingredients.append(
                        {"name": name, "amount": amount, "unit": unit}
                    )

            raw_tags = meta_args.get("tags") or []
            tags = [t for t in raw_tags if t]

            servings = self.__safe_int(meta_args.get("servings"), 2)
            cook_time = self.__safe_int(meta_args.get("cook_time"), 30)

            return MetaResponse(
                description=description,
                ingredients=ingredients,
                tags=tags,
                servings=servings,
                cook_time=cook_time,
            )

        except genai_errors.ClientError as e:
            self.logger.error(f"Gemini API invoke failed (meta): {e}")
            raise MetaException(MetaErrorCode.META_BEDROCK_INVOKE_FAILED)
        except MetaException:
            raise
        except Exception as e:
            self.logger.error(f"Meta extraction failed: {e}")
            raise MetaException(MetaErrorCode.META_EXTRACT_FAILED)

    def extract(self, captions: str) -> MetaResponse:
        prompt = self.extract_prompt.replace("{{ captions }}", captions)
        return self.__converse(prompt)
