import json
import logging
from pathlib import Path
from typing import Dict, Any

from google import genai
from google.genai import types

from app.verify.exception import VerifyException, VerifyErrorCode

logger = logging.getLogger(__name__)

class VerifyGenerator:
    def __init__(
        self,
        client: genai.Client,
        model: str,
        verify_user_prompt_path: Path,
        verify_tool_path: Path,
    ):
        self.client = client
        self.model = model
        self.verify_user_prompt_path = verify_user_prompt_path
        self.verify_tool_path = verify_tool_path
        
        self._load_resources()

    def _load_resources(self):
        try:
            self.prompt_text = self.verify_user_prompt_path.read_text(encoding="utf-8")
            self.tool_def = json.loads(self.verify_tool_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"[VerifyGenerator] 리소스 로딩 실패: {e}")
            raise RuntimeError(f"Failed to load verify resources: {e}")

    def generate(self, file_uri: str, mime_type: str = "video/mp4") -> Dict[str, Any]:
        try:
            # Part 객체 생성
            part_text = types.Part.from_text(text=self.prompt_text)
            part_video = types.Part.from_uri(file_uri=file_uri, mime_type=mime_type)
            
            contents = [
                types.Content(
                    role="user",
                    parts=[part_video, part_text]
                )
            ]

            logger.info(f"[VerifyGenerator] ▶ Gemini API 호출 시도 (Tool Calling) | model={self.model}")
            
            # models.generate_content 호출
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(
                        function_declarations=[
                            types.FunctionDeclaration(
                                name=self.tool_def["name"],
                                description=self.tool_def["description"],
                                parameters=self.tool_def["parameters"]
                            )
                        ]
                    )],
                    tool_config=types.ToolConfig(
                        function_calling_config=types.FunctionCallingConfig(
                            mode="ANY", # 반드시 툴을 호출하도록 강제
                            allowed_function_names=[self.tool_def["name"]]
                        )
                    )
                )
            )

            # Tool Call 응답 파싱
            function_call = None
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        function_call = part.function_call
                        break
            
            if not function_call:
                logger.error(f"[VerifyGenerator] ▶ Gemini가 툴을 호출하지 않음 | response={response}")
                raise VerifyException(VerifyErrorCode.VERIFY_FAILED, "Gemini가 검증 결과를 반환하지 않았습니다.")

            return function_call.args

        except VerifyException:
            raise
        except Exception as e:
            logger.error(f"[VerifyGenerator] ▶ Gemini API 호출 중 오류 발생 | error={e}")
            raise VerifyException(VerifyErrorCode.VERIFY_FAILED, f"Gemini API 호출 실패: {e}")
