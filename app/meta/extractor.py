import json
import logging
from pathlib import Path
from typing import Any, Iterable, List, Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.enum import LanguageType
from app.meta.exception import MetaErrorCode, MetaException
from app.meta.schema import Ingredient, MetaResponse


class MetaExtractor:
    VIDEO_META_FN = "emit_video_meta"
    INGREDIENTS_FN = "emit_ingredients"
    TAGS_KR = "[한식, 중식, 일식, 양식, 분식, 디저트, 간편식, 유아식, 건강식]"
    TAGS_EN = "[Korean, Chinese, Japanese, Western, Street Food, Dessert, Quick Meals, Baby Food, Healthy]"

    def __init__(
        self,
        *,
        client: genai.Client,
        model: str,
        fallback_model: str = "gemini-3.0-flash",
        extract_ingredient_prompt_path: Path,
        extract_ingredient_tool_path: Path,
        video_extract_prompt_path: Optional[Path] = None,
        video_extract_tool_path: Optional[Path] = None,
    ):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.model = model
        self.fallback_model = fallback_model

        # ----- 프롬프트 / 툴 스펙 로드 -----
        self.extract_ingredient_prompt = extract_ingredient_prompt_path.read_text(
            encoding="utf-8"
        )

        extract_ingredient_tool_spec = json.loads(
            extract_ingredient_tool_path.read_text(encoding="utf-8")
        )

        self.system_instruction = (
            "You must call the provided function only. Do not output any free-form text.\n"
        )

        self.ingredients_tool = self._build_tool_from_spec(extract_ingredient_tool_spec)

        self.ingredients_conf = self._build_conf(
            tool=self.ingredients_tool,
            allowed_fn=self.INGREDIENTS_FN,
        )

        self.video_extract_prompt = video_extract_prompt_path.read_text(encoding="utf-8")
        video_extract_tool_spec = json.loads(video_extract_tool_path.read_text(encoding="utf-8"))
        self.video_meta_tool = self._build_tool_from_spec(video_extract_tool_spec)
        self.video_meta_conf = self._build_conf(
            tool=self.video_meta_tool,
            allowed_fn=self.VIDEO_META_FN,
        )


    @staticmethod
    def _build_tool_from_spec(tool_list: list) -> types.Tool:
        if not tool_list:
            raise ValueError("Tool spec list is empty")

        tool_spec = tool_list[0].get("toolSpec") or {}
        name = tool_spec.get("name")
        description = tool_spec.get("description", "")
        json_schema = (tool_spec.get("inputSchema") or {}).get("json") or {}

        if not name:
            raise ValueError("toolSpec.name is required in tool spec JSON")

        fn_decl = types.FunctionDeclaration(
            name=name,
            description=description,
            parameters=json_schema
        )
        return types.Tool(function_declarations=[fn_decl])

    def _build_conf(self, *, tool: types.Tool, allowed_fn: str) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.0,
            tools=[tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=[allowed_fn],
                )
            ),
        )

    @staticmethod
    def _render_prompt(template: str, **vars: str) -> str:
        out = template
        for k, v in vars.items():
            out = out.replace(f"{{{{ {k} }}}}", v)

        return out

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _iter_function_calls(response) -> Iterable[Any]:
        calls = getattr(response, "function_calls", None) or []
        if calls:
            return calls

        if getattr(response, "candidates", None):
            out: list[Any] = []
            for cand in response.candidates:
                content = getattr(cand, "content", None)
                if not content:
                    continue
                for part in getattr(content, "parts", []) or []:
                    fc = getattr(part, "function_call", None)
                    if fc:
                        out.append(fc)
            return out

        return []

    @classmethod
    def _find_call_args(cls, calls: Iterable[Any], fn_name: str) -> dict:
        for call in calls:
            if getattr(call, "name", None) == fn_name:
                return call.args or {}
        return {}

    @staticmethod
    def _is_rate_limit_error(err: Exception) -> bool:
        status_code = getattr(err, "status_code", None)
        if status_code == 429:
            return True

        code = getattr(err, "code", None)
        if code == 429:
            return True

        message = str(err).lower()
        return (
            "429" in message
            or "too many requests" in message
            or "rate limit" in message
            or "resource_exhausted" in message
        )

    def _invoke_generate_content(
        self,
        *,
        contents: Any,
        conf: types.GenerateContentConfig,
        err_code: MetaErrorCode,
    ):
        try:
            return self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=conf,
            )
        except genai_errors.ClientError as e:
            should_fallback = (
                self.fallback_model
                and self.fallback_model != self.model
                and self._is_rate_limit_error(e)
            )
            if should_fallback:
                self.logger.warning(
                    f"Primary Gemini model rate-limited. fallback model={self.fallback_model}"
                )
                try:
                    return self.client.models.generate_content(
                        model=self.fallback_model,
                        contents=contents,
                        config=conf,
                    )
                except genai_errors.ClientError as fallback_error:
                    self.logger.exception("Gemini fallback model invoke failed")
                    raise MetaException(MetaErrorCode.META_API_INVOKE_FAILED) from fallback_error
                except Exception as fallback_error:
                    self.logger.exception("Unexpected error during Gemini fallback call")
                    raise MetaException(err_code) from fallback_error

            self.logger.exception("Gemini API invoke failed")
            raise MetaException(MetaErrorCode.META_API_INVOKE_FAILED) from e
        except Exception as e:
            self.logger.exception("Unexpected error during Gemini call")
            raise MetaException(err_code) from e


    def _generate_content(self, *, prompt: str, conf: types.GenerateContentConfig, err_code: MetaErrorCode):
        return self._invoke_generate_content(
            contents=prompt,
            conf=conf,
            err_code=err_code,
        )


    def extract_ingredients_from_description(
        self,
        description: str,
        channel_owner_top_level_comments: List[str],
        language: LanguageType
    ) -> List[Ingredient]:
        prompt = self._render_prompt(
            self.extract_ingredient_prompt,
            description=description,
            channel_owner_top_level_comments="\n".join(channel_owner_top_level_comments),
            language=language
        )

        try:
            response = self._generate_content(
                prompt=prompt,
                conf=self.ingredients_conf,
                err_code=MetaErrorCode.META_INGREDIENTS_EXTRACT_FAILED,
            )

            calls = self._iter_function_calls(response)
            args = self._find_call_args(calls, self.INGREDIENTS_FN)

            arr = args.get("ingredients") or []
            out: List[Ingredient] = []

            for ing in arr:
                name = (ing.get("name") or "").strip()
                if not name:
                    continue
                amount = self._safe_float(ing.get("amount"), 0.0)
                unit = ing.get("unit") or ""
                out.append(Ingredient(name=name, amount=amount, unit=unit))

            return out

        except MetaException:
            return []

    def extract_video(
        self,
        file_uri: str,
        mime_type: str,
        language: LanguageType,
        original_title: str,
    ) -> MetaResponse:
        if not self.video_extract_prompt or not self.video_meta_conf:
            raise MetaException(MetaErrorCode.META_EXTRACT_FAILED, "Video extraction not configured")

        if language == LanguageType.KR:
            tag_options = self.TAGS_KR
        else:
            tag_options = self.TAGS_EN

        prompt = self._render_prompt(
            self.video_extract_prompt,
            language=language.value,
            tag_options=tag_options,
            original_title=original_title,
        )

        response = self._invoke_generate_content(
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_uri(file_uri=file_uri, mime_type=mime_type),
                        types.Part.from_text(text=prompt),
                    ]
                )
            ],
            conf=self.video_meta_conf,
            err_code=MetaErrorCode.META_EXTRACT_FAILED,
        )

        calls = self._iter_function_calls(response)
        args = self._find_call_args(calls, self.VIDEO_META_FN)
        if not args:
            raise MetaException(MetaErrorCode.META_EXTRACT_FAILED)

        title = (args.get("title") or "").strip()
        description = (args.get("description") or "").strip()

        raw_ingredients = args.get("ingredients") or []
        ingredients = []
        for ing in raw_ingredients:
            name = (ing.get("name") or "").strip()
            if not name:
                continue
            ingredients.append(
                {
                    "name": name,
                    "amount": self._safe_float(ing.get("amount"), 0.0),
                    "unit": ing.get("unit") or "",
                }
            )

        raw_tags = args.get("tags") or []
        tags = [tag.replace(" ", "") for tag in raw_tags if tag]

        servings = self._safe_int(args.get("servings"), 2)
        cook_time = self._safe_int(args.get("cook_time"), 30)

        return MetaResponse(
            title=title,
            description=description,
            ingredients=ingredients,
            tags=tags,
            servings=servings,
            cook_time=cook_time,
        )
