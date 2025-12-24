import json
import logging
from pathlib import Path
from typing import List

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.enum import LanguageType
from app.step.exception import StepErrorCode, StepException
from app.step.schema import StepGroup


class StepGenerator:
    ALLOWED_FUNCTION_NAME = "emit_steps"

    def __init__(
        self,
        *,
        client: genai.Client,
        model: str,
        step_tool_path: Path,
        summarize_user_prompt_path: Path,
        merge_user_prompt_path: Path,
    ):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.model = model

        self.summarize_user_prompt = summarize_user_prompt_path.read_text(encoding="utf-8")
        self.merge_user_prompt = merge_user_prompt_path.read_text(encoding="utf-8")

        step_tool_spec = json.loads(step_tool_path.read_text(encoding="utf-8"))
        self.step_tool = self._build_tool_from_spec(step_tool_spec)

        self.system_instruction = (
            "You must respond by calling one of the provided functions. "
            "Do not generate natural language text outside of a function call. "
            "If a function call is not applicable, still return a function call with best-effort arguments.\n"
            "All outputs must be valid UTF-8. "
            "Ensure complete Unicode characters and avoid truncated or malformed text."
        )

        self.step_conf = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.0,
            tools=[self.step_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=[self.ALLOWED_FUNCTION_NAME],
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

        fn_decl = {"name": name, "description": description, "parameters": json_schema}
        return types.Tool(function_declarations=[fn_decl])

    @staticmethod
    def _render_prompt(template: str, **vars: str) -> str:
        out = template
        for k, v in vars.items():
            out = out.replace(f"{{{{ {k} }}}}", v)
        return out

    def _call_for_steps(self, user_prompt: str) -> List[StepGroup]:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=self.step_conf,
            )
            step_args = self._extract_emit_steps_args(response)
            return self._parse_steps(step_args)

        except genai_errors.ClientError as e:
            self.logger.exception("Gemini API 호출 중 오류가 발생했습니다.")
            raise StepException(StepErrorCode.STEP_GENERATE_FAILED) from e
        except StepException:
            raise
        except Exception as e:
            self.logger.exception("단계 생성 중 예기치 못한 오류가 발생했습니다.")
            raise StepException(StepErrorCode.STEP_GENERATE_FAILED) from e

    def _extract_emit_steps_args(self, response) -> dict:
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
            if getattr(call, "name", None) == self.ALLOWED_FUNCTION_NAME:
                return call.args

        self.logger.error("Gemini API 응답을 처리할 수 없습니다.")
        raise StepException(StepErrorCode.STEP_GENERATE_FAILED)

    def _parse_steps(self, step_args: dict) -> List[StepGroup]:
        raw_steps = step_args.get("steps") or []
        try:
            return [StepGroup(**s) for s in raw_steps]
        except Exception as e:
            self.logger.exception("Gemini API 응답 형식이 올바르지 않습니다.")
            raise StepException(StepErrorCode.STEP_GENERATE_FAILED) from e

    def summarize(self, captions_json_str: str, language: LanguageType) -> List[StepGroup]:
        user_prompt = self._render_prompt(
            self.summarize_user_prompt,
            captions=captions_json_str,
            language=language.value,
        )
        return self._call_for_steps(user_prompt)

    def merge(self, flat_steps_json_str: str, language: LanguageType) -> List[StepGroup]:
        user_prompt = self._render_prompt(
            self.merge_user_prompt,
            steps=flat_steps_json_str,
            language=language.value,
        )
        return self._call_for_steps(user_prompt)
