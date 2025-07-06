import json
from importlib import resources
from typing import Dict, List, Optional

import jinja2
from openai import OpenAI

from app.models.recipe import Ingredient
from app.services.base import BaseAIService


class IngredientsService(BaseAIService):
    """재료 추출 서비스"""

    def __init__(self, openai_client: Optional[OpenAI] = None, model_name: str = "gpt-4o-mini"):
        super().__init__(openai_client, model_name)
        self.template_env = self._setup_template_env()

    def _setup_template_env(self) -> jinja2.Environment:
        """템플릿 환경 설정"""
        def load_template(name: str) -> str:
            return resources.files("app.prompts.user").joinpath(name).read_text()

        return jinja2.Environment(
            loader=jinja2.FunctionLoader(load_template), 
            autoescape=False
        )

    def extract_ingredients(
        self, captions: List[Dict], description: str = ""
    ) -> List[Ingredient]:
        """자막과 설명에서 재료 리스트를 추출"""
        try:
            system_prompt = self._get_system_prompt()
            user_prompt = self._create_user_prompt(captions, description)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,  # type: ignore
                max_tokens=2048,
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            result = response.choices[0].message.content
            if not result:
                return []

            return self._parse_ingredients_response(result.strip())

        except Exception as e:
            self.logger.exception("재료 추출 중 오류 발생")
            return []

    def _get_system_prompt(self) -> str:
        """시스템 프롬프트 반환"""
        return """당신은 요리 영상의 자막에서 재료를 추출하는 전문가입니다.
자막 내용을 분석해서 요리에 사용되는 재료들을 JSON 형태로 추출해주세요.

응답 형식:
{
  "ingredients": [
    {"name": "재료명", "amount": 수량(숫자), "unit": "단위"},
    {"name": "재료명", "amount": null, "unit": null}
  ]
}

- amount와 unit이 명시되지 않은 경우 null로 설정
- 재료명은 한국어로 정규화
- 수량은 숫자만 입력"""

    def _create_user_prompt(self, captions: List[Dict], description: str) -> str:
        """사용자 프롬프트 생성"""
        caption_text = " ".join([seg.get("text", "") for seg in captions])

        return f"""
자막 내용:
{caption_text}

영상 설명:
{description}

위 내용에서 요리에 사용되는 재료들을 추출해주세요.
"""

    def _parse_ingredients_response(self, response: str) -> List[Ingredient]:
        """AI 응답을 파싱하여 Ingredient 객체 리스트로 변환"""
        try:
            data = json.loads(response)
            ingredients = []

            for item in data.get("ingredients", []):
                ingredient = Ingredient(
                    name=item.get("name", ""),
                    amount=item.get("amount"),
                    unit=item.get("unit")
                )
                ingredients.append(ingredient)

            return ingredients

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 파싱 오류: {e}")
            return []


# 하위 호환성을 위한 함수 (추후 제거 예정)
def extract_ingredients(
    captions: List[Dict], description: str = "", client: Optional[OpenAI] = None
) -> List[Ingredient]:
    """@deprecated: IngredientsService.extract_ingredients() 사용 권장"""
    service = IngredientsService(client)
    return service.extract_ingredients(captions, description) 