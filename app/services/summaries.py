"""조리 단계 요약 생성 서비스"""

import json
from typing import List, Optional

from openai import OpenAI

from app.constants import AIConfig, ErrorMessages
from app.models.captions import CaptionResponse
from app.models.ingredients import Ingredient
from app.models.summaries import CookingProcessSummary
from app.services.base import BaseAIService, TemplateService


class SummariesService(BaseAIService):
    """조리 단계 요약 생성 서비스"""

    def __init__(self, openai_client: Optional[OpenAI] = None, model_name: Optional[str] = None):
        super().__init__(openai_client, model_name or AIConfig.DEFAULT_MODEL)

    async def create_summary(
        self, 
        video_id: str, 
        video_type: str, 
        caption_response: CaptionResponse, 
        ingredients: List[Ingredient]
    ) -> Optional[CookingProcessSummary]:
        """자막과 재료 정보를 기반으로 조리 단계 요약을 생성합니다."""
        try:
            ai_response = self._generate_ai_summary(caption_response, ingredients)
            if not ai_response:
                return None
            
            summary_data = json.loads(ai_response)
            cooking_summary = CookingProcessSummary(
                description=summary_data.get("description", ""),
                steps=summary_data.get("steps", [])
            )

            return cooking_summary

        except json.JSONDecodeError as parsing_error:
            self.logger.error(f"JSON 파싱 오류: {parsing_error}")
            return None
        except Exception as unexpected_error:
            self.logger.exception(f"조리 단계 요약 생성 중 오류: {unexpected_error}")
            return None

    def _generate_ai_summary(
        self, 
        caption_response: CaptionResponse, 
        ingredients: List[Ingredient]
    ) -> Optional[str]:
        """AI를 사용하여 조리 단계 요약을 생성합니다."""
        try:
            system_prompt = TemplateService.load_system_prompt("summaries.md")
            user_prompt = self._create_user_prompt(caption_response, ingredients)

            chat_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            ai_result = self._create_chat_completion(
                messages=chat_messages,
                response_format={"type": "json_object"}
            )

            return ai_result or ErrorMessages.SUMMARY_EMPTY

        except Exception as generation_error:
            self.logger.exception("AI 요약 생성 중 오류 발생")
            return ErrorMessages.SUMMARY_FAILED

    def _create_user_prompt(
        self, 
        caption_response: CaptionResponse, 
        ingredients: List[Ingredient]
    ) -> str:
        """사용자 프롬프트를 생성합니다."""
        template = self.template_env.get_template("summaries.jinja2")
        return template.render(
            captions=caption_response.captions, 
            lang_code=caption_response.lang_code,
            ingredients=ingredients
        ) 