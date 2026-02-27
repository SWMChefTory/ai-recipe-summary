import json
import logging
import re
from pathlib import Path
from typing import Any, List

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.enum import LanguageType
from app.gemini_safety import relaxed_safety_settings
from app.step.exception import StepErrorCode, StepException
from app.step.schema import StepGroup


class StepGenerator:
    VIDEO_ALLOWED_FUNCTION_NAME = "emit_recipe_steps"
    TIMECODE_PATTERN = re.compile(r"^\d{2}:[0-5]\d:[0-5]\d$")

    def __init__(
        self,
        *,
        client: genai.Client,
        model: str,
        fallback_model: str = "gemini-3.0-flash",
        video_step_tool_path: Path,
        video_summarize_user_prompt_path: Path,
    ):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.model = model
        self.fallback_model = fallback_model

        self.video_summarize_user_prompt = video_summarize_user_prompt_path.read_text(encoding="utf-8")
        video_step_tool_spec = json.loads(video_step_tool_path.read_text(encoding="utf-8"))
        self.video_step_tool = self._build_tool_from_spec(video_step_tool_spec)
        
        self.video_step_conf = types.GenerateContentConfig(
            temperature=0.0,
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
            safety_settings=relaxed_safety_settings(),
            tools=[self.video_step_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=[self.VIDEO_ALLOWED_FUNCTION_NAME],
                )
            ),
        )

    @staticmethod
    def _build_tool_from_spec(tool_list: list) -> types.Tool:
        if not tool_list:
            raise ValueError("Step tool spec list is empty")

        tool_spec = tool_list[0].get("toolSpec") or {}
        name = tool_spec.get("name")
        description = tool_spec.get("description", "")
        json_schema = (tool_spec.get("inputSchema") or {}).get("json") or {}

        if not name:
            raise ValueError("toolSpec.name is required in step tool spec JSON")

        fn_decl = types.FunctionDeclaration(
            name=name,
            description=description,
            parameters=json_schema
        )
        return types.Tool(function_declarations=[fn_decl])

    @staticmethod
    def _render_prompt(template: str, **vars: str) -> str:
        out = template
        for k, v in vars.items():
            out = out.replace(f"{{{{ {k} }}}}", v)
        return out

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

    def _generate_content(self, *, model: str, contents, config: types.GenerateContentConfig):
        return self.client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

    def _extract_emit_steps_args(self, response, allowed_function_name: str) -> dict:
        calls = getattr(response, "function_calls", None) or []

        if not calls and getattr(response, "candidates", None):
            for cand in response.candidates:
                content = getattr(cand, "content", None)
                if not content:
                    continue
                for part in getattr(content, "parts", []) or []:
                    fc = getattr(part, "function_call", None)
                    if fc:
                        calls.append(fc)

        for call in calls:
            if getattr(call, "name", None) == allowed_function_name:
                return call.args

        self.logger.error("Gemini API 응답을 처리할 수 없습니다.")
        raise StepException(StepErrorCode.STEP_GENERATE_FAILED)

    @classmethod
    def _timecode_to_seconds(cls, value: Any, *, path: str) -> int:
        if not isinstance(value, str):
            raise StepException(
                StepErrorCode.STEP_GENERATE_FAILED,
                f"Invalid timestamp type at {path}: {type(value)}",
            )
        raw = value.strip()
        if not cls.TIMECODE_PATTERN.fullmatch(raw):
            raise StepException(
                StepErrorCode.STEP_GENERATE_FAILED,
                f"Invalid timestamp format at {path}: {value}",
            )

        hh_str, mm_str, ss_str = raw.split(":")
        return (int(hh_str) * 3600) + (int(mm_str) * 60) + int(ss_str)

    def _normalize_step_args(self, step_args: dict) -> dict:
        raw_steps = step_args.get("steps")
        if not isinstance(raw_steps, list):
            raise StepException(StepErrorCode.STEP_GENERATE_FAILED, "steps must be an array")

        normalized_steps = []
        for i, step in enumerate(raw_steps):
            if not isinstance(step, dict):
                raise StepException(StepErrorCode.STEP_GENERATE_FAILED, f"steps[{i}] must be an object")

            descriptions = step.get("descriptions")
            if not isinstance(descriptions, list):
                raise StepException(
                    StepErrorCode.STEP_GENERATE_FAILED,
                    f"steps[{i}].descriptions must be an array",
                )

            normalized_descriptions = []
            for j, desc in enumerate(descriptions):
                if not isinstance(desc, dict):
                    raise StepException(
                        StepErrorCode.STEP_GENERATE_FAILED,
                        f"steps[{i}].descriptions[{j}] must be an object",
                    )
                normalized_desc = dict(desc)
                normalized_desc["start"] = self._timecode_to_seconds(
                    desc.get("start"),
                    path=f"steps[{i}].descriptions[{j}].start",
                )
                normalized_descriptions.append(normalized_desc)

            normalized_step = dict(step)
            normalized_step["start"] = self._timecode_to_seconds(
                step.get("start"),
                path=f"steps[{i}].start",
            )
            normalized_step["descriptions"] = normalized_descriptions
            normalized_steps.append(normalized_step)

        return {"steps": normalized_steps}

    def _parse_steps(self, step_args: dict) -> List[StepGroup]:
        raw_steps = step_args.get("steps") or []
        try:
            return [StepGroup(**s) for s in raw_steps]
        except Exception as e:
            self.logger.exception("Gemini API 응답 형식이 올바르지 않습니다.")
            raise StepException(StepErrorCode.STEP_GENERATE_FAILED) from e

    def summarize_video(self, file_uri: str, mime_type: str, language: LanguageType) -> List[StepGroup]:
        if not self.video_summarize_user_prompt or not self.video_step_conf:
             raise StepException(StepErrorCode.STEP_GENERATE_FAILED, "Video summarization is not configured.")

        user_prompt = self._render_prompt(
            self.video_summarize_user_prompt,
            language=language.value,
        )
        contents = [
            types.Content(
                parts=[
                    types.Part.from_uri(file_uri=file_uri, mime_type=mime_type),
                    types.Part.from_text(text=user_prompt),
                ]
            )
        ]

        try:
            try:
                response = self._generate_content(
                    model=self.model,
                    contents=contents,
                    config=self.video_step_conf,
                )
            except genai_errors.ClientError as e:
                should_fallback = (
                    self.fallback_model
                    and self.fallback_model != self.model
                    and self._is_rate_limit_error(e)
                )
                if not should_fallback:
                    raise

                self.logger.warning(
                    f"Primary Gemini model rate-limited. fallback model={self.fallback_model}"
                )
                response = self._generate_content(
                    model=self.fallback_model,
                    contents=contents,
                    config=self.video_step_conf,
                )

            step_args = self._extract_emit_steps_args(response, self.VIDEO_ALLOWED_FUNCTION_NAME)
            normalized_step_args = self._normalize_step_args(step_args)
            return self._parse_steps(normalized_step_args)
        except genai_errors.ClientError as e:
            self.logger.exception("Gemini API 호출 중 오류가 발생했습니다.")
            raise StepException(StepErrorCode.STEP_GENERATE_FAILED) from e
        except StepException:
            raise
        except Exception as e:
            self.logger.exception("단계 생성 중 예기치 못한 오류가 발생했습니다.")
            raise StepException(StepErrorCode.STEP_GENERATE_FAILED) from e
