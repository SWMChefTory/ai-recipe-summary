import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.enum import LanguageType
from app.gemini_safety import relaxed_safety_settings
from app.scene.exception import SceneErrorCode, SceneException


class SceneGenerator:
    ALLOWED_FUNCTION_NAME = "emit_recipe_scenes"
    TIMECODE_PATTERN = re.compile(r"^\d{2}:[0-5]\d:[0-5]\d$")

    def __init__(
        self,
        *,
        client: genai.Client,
        model: str,
        fallback_model: str = "gemini-3.0-flash",
        video_scene_tool_path: Path,
        video_scene_user_prompt_path: Path,
    ):
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.model = model
        self.fallback_model = fallback_model

        self.video_scene_user_prompt = video_scene_user_prompt_path.read_text(encoding="utf-8")
        video_scene_tool_spec = json.loads(video_scene_tool_path.read_text(encoding="utf-8"))
        self.video_scene_tool = self._build_tool_from_spec(video_scene_tool_spec)

        self.video_scene_conf = types.GenerateContentConfig(
            temperature=0.0,
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
            safety_settings=relaxed_safety_settings(),
            thinking_config=types.ThinkingConfig(
                thinkingLevel="HIGH",
            ),
            tools=[self.video_scene_tool],
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
            raise ValueError("Scene tool spec list is empty")

        tool_spec = tool_list[0].get("toolSpec") or {}
        name = tool_spec.get("name")
        description = tool_spec.get("description", "")
        json_schema = (tool_spec.get("inputSchema") or {}).get("json") or {}

        if not name:
            raise ValueError("toolSpec.name is required in scene tool spec JSON")

        fn_decl = types.FunctionDeclaration(
            name=name,
            description=description,
            parameters=json_schema,
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

    @staticmethod
    def _is_server_error(err: Exception) -> bool:
        code = getattr(err, "code", None)
        return code is not None and 500 <= code < 600

    def _generate_content(self, *, model: str, contents, config: types.GenerateContentConfig):
        return self.client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

    def _extract_function_args(self, response) -> dict:
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

        self.logger.error("Gemini API 응답에서 scene 함수 호출을 찾을 수 없습니다.")
        raise SceneException(SceneErrorCode.SCENE_GENERATE_FAILED)

    @classmethod
    def _validate_timecode(cls, value: Any, *, path: str) -> str:
        if not isinstance(value, str):
            raise SceneException(SceneErrorCode.SCENE_GENERATE_FAILED)
        raw = value.strip()
        if not cls.TIMECODE_PATTERN.fullmatch(raw):
            raise SceneException(SceneErrorCode.SCENE_GENERATE_FAILED)
        return raw

    def _validate_scenes(self, scene_args: dict) -> List[Dict[str, Any]]:
        raw_scenes = scene_args.get("scenes")
        if not isinstance(raw_scenes, list):
            raise SceneException(SceneErrorCode.SCENE_GENERATE_FAILED)

        validated = []
        for i, scene in enumerate(raw_scenes):
            if not isinstance(scene, dict):
                raise SceneException(SceneErrorCode.SCENE_GENERATE_FAILED)

            self._validate_timecode(scene.get("start"), path=f"scenes[{i}].start")
            self._validate_timecode(scene.get("end"), path=f"scenes[{i}].end")

            validated.append(scene)

        return validated

    @staticmethod
    def _build_steps_json(steps: List[Dict[str, Any]]) -> str:
        formatted = []
        for i, step in enumerate(steps, start=1):
            formatted.append({
                "step": i,
                "subtitle": step.get("subtitle", ""),
                "start": step.get("start", 0),
                "descriptions": step.get("descriptions", []),
            })
        return json.dumps(formatted, ensure_ascii=False, indent=2)

    def generate_scenes(
        self,
        file_uri: str,
        mime_type: str,
        steps: List[Dict[str, Any]],
        language: LanguageType,
    ) -> List[Dict[str, Any]]:
        if not self.video_scene_user_prompt or not self.video_scene_conf:
            raise SceneException(SceneErrorCode.SCENE_GENERATE_FAILED)

        steps_json = self._build_steps_json(steps)
        user_prompt = self._render_prompt(
            self.video_scene_user_prompt,
            language=language.value,
            steps_json=steps_json,
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
                    config=self.video_scene_conf,
                )
            except (genai_errors.ClientError, genai_errors.ServerError) as e:
                should_fallback = (
                    self.fallback_model
                    and self.fallback_model != self.model
                    and (self._is_rate_limit_error(e) or self._is_server_error(e))
                )
                if not should_fallback:
                    raise

                self.logger.warning(
                    f"Primary Gemini model unavailable. fallback model={self.fallback_model}"
                )
                response = self._generate_content(
                    model=self.fallback_model,
                    contents=contents,
                    config=self.video_scene_conf,
                )

            scene_args = self._extract_function_args(response)
            return self._validate_scenes(scene_args)
        except (genai_errors.ClientError, genai_errors.ServerError) as e:
            self.logger.exception("Gemini API 호출 중 오류가 발생했습니다.")
            raise SceneException(SceneErrorCode.SCENE_GENERATE_FAILED) from e
        except SceneException:
            raise
        except Exception as e:
            self.logger.exception("장면 생성 중 예기치 못한 오류가 발생했습니다.")
            raise SceneException(SceneErrorCode.SCENE_GENERATE_FAILED) from e
