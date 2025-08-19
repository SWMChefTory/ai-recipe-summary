"""재료 추출 서비스"""

import json
from typing import List, Optional

from openai import OpenAI

from app.constants import AIConfig
from app.models.captions import CaptionResponse, CaptionSegment
from app.models.ingredients import Ingredient
from app.services.base import BaseAIService, TemplateService


class IngredientsService(BaseAIService):
    """요리 영상에서 재료 추출 서비스"""

    def __init__(self, openai_client: Optional[OpenAI] = None, model_name: Optional[str] = None) -> None:
        super().__init__(openai_client, model_name or AIConfig.DEFAULT_MODEL)

    def extract_ingredients(
        self, 
        caption_response: CaptionResponse, 
        video_description: str = ""
    ) -> List[Ingredient]:
        """자막과 설명에서 재료 리스트를 추출합니다."""
        try:
            system_prompt = TemplateService.load_system_prompt("ingredients.md")
            user_prompt = self._create_user_prompt(caption_response, video_description)

            chat_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            ai_response = self._create_chat_completion(
                messages=chat_messages,
                max_tokens=2048,
                temperature=0,
                response_format={"type": "json_object"}
            )

            if not ai_response:
                return []

            return self._parse_ingredients_from_response(ai_response)

        except Exception as extraction_error:
            self.logger.exception("재료 추출 중 오류 발생")
            return []

    def _create_user_prompt(
        self, 
        caption_response: CaptionResponse, 
        video_description: str
    ) -> str:
        """사용자 프롬프트를 생성합니다."""
        caption_text = self._extract_text_from_captions(caption_response.captions)
        
        template = self.template_env.get_template("ingredients.jinja2")
        return template.render(
            caption_text=caption_text,
            lang_code=caption_response.lang_code,
            description=video_description
        )

    def _extract_text_from_captions(self, caption_segments: List[CaptionSegment]) -> str:
        """자막 세그먼트에서 텍스트만 추출하여 연결합니다."""
        extracted_texts = []
        for segment in caption_segments:
            text_content = segment.text.strip()
            if text_content:
                extracted_texts.append(text_content)
        return " ".join(extracted_texts)

    def _parse_ingredients_from_response(self, ai_response: str) -> List[Ingredient]:
        """AI 응답을 파싱하여 Ingredient 객체 리스트로 변환합니다."""
        try:
            response_data = json.loads(ai_response)
            parsed_ingredients = []

            for ingredient_item in response_data.get("ingredients", []):
                ingredient_name = ingredient_item.get("name", "").strip()
                if not ingredient_name:
                    continue
                    
                ingredient = Ingredient(
                    name=ingredient_name,
                    amount=ingredient_item.get("amount"),
                    unit=ingredient_item.get("unit")
                )
                parsed_ingredients.append(ingredient)

            return parsed_ingredients

        except json.JSONDecodeError as parsing_error:
            self.logger.error(f"JSON 파싱 오류: {parsing_error}")
            return []
        except Exception as unexpected_error:
            self.logger.error(f"재료 파싱 중 오류: {unexpected_error}")
            return []

