import json
import logging
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.caption.exception import CaptionErrorCode, CaptionException


class CaptionRecipeValidator:
    def __init__(
        self,
        *,
        client: genai.Client,
        model: str,
        max_tokens: int = 64,
        temperature: float = 0.0,
    ):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        base = Path(__file__).parent / "prompt"
        self.template = (base / "recipe_detect.md").read_text(encoding="utf-8")
        self.tools = json.loads((base / "emit_bit_tool.json").read_text(encoding="utf-8"))

        self.system_instruction = (
            "You must call the provided function only. Do not produce free-form text.\n"
            "All natural-language must be Korean when applicable. Use proper UTF-8 "
            "encoding for all Korean characters. Ensure complete Unicode characters, "
            "especially for syllables like 좋, 않, 됐, etc."
        )

        def _build_tool_from_spec(tool_list: list) -> types.Tool:
            if not tool_list:
                raise ValueError("Validator tool spec list is empty")

            tool_spec = tool_list[0].get("toolSpec") or {}
            name = tool_spec.get("name")
            description = tool_spec.get("description", "")
            json_schema = (tool_spec.get("inputSchema") or {}).get("json") or {}

            if not name:
                raise ValueError("toolSpec.name is required in validator tool spec JSON")

            fn_decl = {
                "name": name,
                "description": description,
                "parameters": json_schema,
            }

            return types.Tool(function_declarations=[fn_decl])

        def _get_function_name(tool_list: list) -> Optional[str]:
            try:
                return tool_list[0].get("toolSpec", {}).get("name")
            except Exception:
                return None

        self.tool_name = _get_function_name(self.tools)
        self.validator_tool = _build_tool_from_spec(self.tools)
        allowed_functions = [self.tool_name] if self.tool_name else []
        self.validator_conf = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=self.temperature,
            tools=[self.validator_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=allowed_functions or None,
                )
            ),
        )

    def __converse(self, user_prompt: str) -> Optional[int]:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=self.validator_conf,
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
                self.logger.error("No function call returned from Gemini (emit_bit)")
                return None

            bit_arg = None
            for call in calls:
                if call.name == self.tool_name:
                    args = call.args or {}
                    bit_arg = args.get("bit")
                    break

            if bit_arg is None:
                self.logger.error("emit_bit not found in function calls")
                return None

            try:
                return int(bit_arg)
            except Exception:
                self.logger.error(f"emit_bit returned non-integer: {bit_arg}")
                return None

        except genai_errors.ClientError as e:
            self.logger.error(f"Gemini API failed (emit_bit): {e}")
            raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)
        except Exception as e:
            self.logger.error(f"Unexpected error while calling Gemini: {e}")
            raise CaptionException(CaptionErrorCode.CAPTION_EXTRACT_FAILED)

        return None

    def validate(self, captions: str, lang_code: str, video_id: str):
        try:
            # 1) 프롬프트 채우기
            prompt = (
                self.template.replace("{{ lang_code }}", lang_code)
                             .replace("{{ captions }}", captions)
            )

            # 2) Gemini 호출
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
