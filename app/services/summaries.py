import logging
from importlib import resources
from typing import Dict, List, Optional

import jinja2
from openai import OpenAI

from app.services.base import BaseAIService


class SummaryService(BaseAIService):
    """요약 생성 서비스"""

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

    def summarize(self, captions: List[Dict], description: str) -> str:
        """자막과 설명을 기반으로 레시피 요약 생성"""
        try:
            tpl = self.template_env.get_template("recipe.jinja2")
            system_prompt = self._get_system_prompt()
            user_prompt = tpl.render(captions=captions, description=description)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,  # type: ignore
                max_tokens=4096,
                temperature=0.5,
                response_format={"type": "json_object"},
            )

            result = response.choices[0].message.content
            if not result:
                return "[요약 결과가 비어 있습니다]"
            return result.strip()

        except Exception as e:
            self.logger.exception("요약 생성 중 오류 발생")
            return "[요약 실패: 문제가 발생했습니다]"

    def _get_system_prompt(self) -> str:
        """시스템 프롬프트 반환"""
        return resources.files("app.prompts.system").joinpath("recipe.txt").read_text()


# 하위 호환성을 위한 함수 (추후 제거 예정)
def load_template(name: str) -> str:
    """@deprecated: SummaryService._setup_template_env() 사용 권장"""
    return resources.files("app.prompts.user").joinpath(name).read_text()


def summarize(captions: List[Dict], description: str, client: Optional[OpenAI] = None) -> str:
    """@deprecated: SummaryService.summarize() 사용 권장"""
    service = SummaryService(client)
    return service.summarize(captions, description)
