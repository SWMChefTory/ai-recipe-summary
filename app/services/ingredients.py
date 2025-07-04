import logging
from importlib import resources
from typing import Dict, List

import jinja2
from openai import OpenAI

from app.models.recipe import Ingredient

logger = logging.getLogger(__name__)
MODEL_NAME = "gpt-4o-mini"

client = OpenAI()

def load_template(name: str) -> str:
    return resources.files("app.prompts.user").joinpath(name).read_text()

env = jinja2.Environment(loader=jinja2.FunctionLoader(load_template), autoescape=False)

def extract_ingredients(captions: List[Dict], description: str = "", client: OpenAI = client) -> List[Ingredient]:
    """자막과 설명에서 재료 리스트를 추출"""
    try:
        # 재료 추출용 프롬프트 (간단한 시스템 프롬프트 사용)
        system_prompt = """당신은 요리 영상의 자막에서 재료를 추출하는 전문가입니다.
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

        # 자막 텍스트 추출
        caption_text = " ".join([seg.get("text", "") for seg in captions])
        
        user_prompt = f"""
자막 내용:
{caption_text}

영상 설명:
{description}

위 내용에서 요리에 사용되는 재료들을 추출해주세요.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,  # type: ignore
            max_tokens=2048,
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        result = response.choices[0].message.content
        if not result:
            return []
        result = result.strip()
        
        # JSON 파싱 및 Ingredient 객체로 변환
        import json
        data = json.loads(result)
        ingredients = []
        
        for item in data.get("ingredients", []):
            ingredient = Ingredient(
                name=item.get("name", ""),
                amount=item.get("amount"),
                unit=item.get("unit")
            )
            ingredients.append(ingredient)
        
        return ingredients

    except Exception as e:
        logger.exception("재료 추출 중 오류 발생")
        return [] 