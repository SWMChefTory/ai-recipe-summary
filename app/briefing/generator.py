import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.briefing.exception import BriefingErrorCode, BriefingException
from app.enum import LanguageType


class IBriefingGenerator(ABC):
    """레시피 관련 댓글 필터링 및 브리핑 생성을 담당하는 인터페이스"""

    @abstractmethod
    def generate(self, comments: List[str]) -> List[str]:
        """
        댓글(List[str])을 입력받아 브리핑 문장 리스트를 반환.
        - 레시피 관련 2~5문장
        - 2개 미만이면 빈 리스트 반환
        """
        pass

class BriefingGenerator(IBriefingGenerator):
    def __init__(
        self,
        *,
        client: genai.Client,
        model: str,
        generate_user_prompt_path: Path,
        generate_tool_path: Path,
    ):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.model = model

        self.briefing_prompt = generate_user_prompt_path.read_text(encoding="utf-8")
        self.briefing_tool_spec = json.loads(generate_tool_path.read_text(encoding="utf-8"))

        self.system_instruction = (
            "You are a specialized AI assistant for summarizing cooking review. "
            "You must ONLY call the provided function (`emit_briefing`) with the extracted data. "
            "Do not output any conversational text, markdown blocks, or explanations outside the function call."
        )

        def _build_tool_from_spec(tool_list: list) -> types.Tool:
            if not tool_list:
                raise ValueError("Briefing tool spec list is empty")

            tool_spec = tool_list[0].get("toolSpec") or {}
            name = tool_spec.get("name")
            description = tool_spec.get("description", "")
            json_schema = (tool_spec.get("inputSchema") or {}).get("json") or {}

            if not name:
                raise ValueError("toolSpec.name is required in briefing tool spec JSON")

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

        self.tool_name = _get_function_name(self.briefing_tool_spec)
        self.briefing_tool = _build_tool_from_spec(self.briefing_tool_spec)

        allowed_functions = [self.tool_name] if self.tool_name else []
        self.briefing_conf = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.0,
            tools=[self.briefing_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=allowed_functions or None,
                )
            ),
        )

    def __converse_briefing(self, user_prompt: str) -> List[str]:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=self.briefing_conf,
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
                self.logger.error("No function call returned from Gemini (emit_briefing)")
                return []

            briefing_args = None
            for call in calls:
                if call.name == self.tool_name:
                    briefing_args = call.args or {}
                    break

            if not briefing_args:
                self.logger.error("emit_briefing not found in function calls")
                return []

            items = briefing_args.get("items") or []
            return [str(item) for item in items if isinstance(item, str)]

        except genai_errors.ClientError as e:
            self.logger.error(f"Gemini API failed (emit_briefing): {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected converse response (emit_briefing): {e}")
            return []


    def generate(self, comments: List[str], language: LanguageType) -> List[str]:
        try:
            comments_json = json.dumps(
                [comment for comment in comments if isinstance(comment, str) and comment.strip()],
                ensure_ascii=False
            )
            prompt = (
                self.briefing_prompt
                .replace("{{ comments_json }}", comments_json)
                .replace("{{ language }}", language)
            )
            result = self.__converse_briefing(prompt)

            if len(result) > 4:
                result = result[:4]

            if len(result) < 2:
                return []

            return result

        except Exception as e:
            self.logger.error(f'브리핑 생성 중 오류가 발생했습니다: {e}')
            raise BriefingException(BriefingErrorCode.BRIEFING_GENERATE_FAILED)
