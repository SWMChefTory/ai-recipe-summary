import json
import logging
from pathlib import Path
from typing import List, Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.step.exception import StepErrorCode, StepException
from app.step.schema import StepGroup


class StepGenerator:
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

        self.step_tool_spec = json.loads(step_tool_path.read_text(encoding="utf-8"))

        self.system_instruction = (
            "You must call the provided function only. Do not produce free-form text.\n"
            "All natural-language must be Korean. Use proper UTF-8 encoding for all "
            "Korean characters. Ensure complete Unicode characters, especially for "
            "Korean syllables like 좋, 않, 됐, etc."
        )

        def _build_tool_from_spec(tool_list: list) -> types.Tool:
            if not tool_list:
                raise ValueError("Step tool spec list is empty")

            tool_spec = tool_list[0].get("toolSpec") or {}
            name = tool_spec.get("name")
            description = tool_spec.get("description", "")
            json_schema = (tool_spec.get("inputSchema") or {}).get("json") or {}

            if not name:
                raise ValueError("toolSpec.name is required in step tool spec JSON")

            fn_decl = {
                "name": name,
                "description": description,
                "parameters": json_schema,
            }

            return types.Tool(function_declarations=[fn_decl])

        self.step_tool = _build_tool_from_spec(self.step_tool_spec)

        self.step_conf = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.0,
            tools=[self.step_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=["emit_steps"],
                )
            ),
        )

    def __call_converse_for_steps(self, user_prompt: str) -> List[StepGroup]:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=self.step_conf,
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
                self.logger.error("No function call returned from Gemini (emit_steps)")
                return []

            step_args = None
            for call in calls:
                if call.name == "emit_steps":
                    step_args = call.args or {}
                    break

            if not step_args:
                self.logger.error("emit_steps not found in function calls")
                return []

            raw_steps = step_args.get("steps") or []
            try:
                return [StepGroup(**s) for s in raw_steps]
            except Exception as e:
                self.logger.error(f"Failed to parse steps into StepGroup: {e}")
                return []

        except genai_errors.ClientError as e:
            self.logger.error(f"Gemini API failed (emit_steps): {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected converse response (emit_steps): {e}")
            return []


    def summarize(self, captions_json_str: str) -> List[StepGroup]:
        user_prompt = self.summarize_user_prompt.replace("{{ captions }}", captions_json_str)
        return self.__call_converse_for_steps(user_prompt)


    def merge(self, flat_steps_json_str: str) -> List[StepGroup]:
        user_prompt = self.merge_user_prompt.replace("{{ steps }}", flat_steps_json_str)
        result = self.__call_converse_for_steps(user_prompt)
        if not result:
            raise StepException(StepErrorCode.STEP_GENERATE_FAILED)
        return result