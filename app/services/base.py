"""서비스 레이어 기본 클래스들"""

import logging
from abc import ABC
from importlib import resources
from typing import Any, Dict, List, Optional

import jinja2
from openai import OpenAI

from app.constants import AIConfig, ErrorMessages

logger = logging.getLogger(__name__)


class BaseService(ABC):
    """모든 서비스 클래스의 기본 클래스"""
    
    def __init__(self, model_name: str = AIConfig.DEFAULT_MODEL) -> None:
        self.model_name = model_name
        self.logger = logger


class TemplateService:
    """템플릿 관련 유틸리티 서비스"""
    
    @staticmethod
    def create_template_environment() -> jinja2.Environment:
        """Jinja2 템플릿 환경을 생성합니다."""
        def load_template(template_name: str) -> str:
            return resources.files("app.prompts.user").joinpath(template_name).read_text()

        return jinja2.Environment(
            loader=jinja2.FunctionLoader(load_template), 
            autoescape=False
        )
    
    @staticmethod
    def load_system_prompt(prompt_filename: str) -> str:
        """시스템 프롬프트 파일을 로드합니다."""
        return resources.files("app.prompts.system").joinpath(prompt_filename).read_text()


class BaseAIService(BaseService):
    """OpenAI API를 사용하는 서비스들의 기본 클래스"""
    
    def __init__(self, openai_client: Optional[OpenAI] = None, model_name: str = AIConfig.DEFAULT_MODEL) -> None:
        super().__init__(model_name)
        self.client = openai_client or OpenAI()
        self.template_env = TemplateService.create_template_environment()
        
        if not self.client:
            raise ValueError(ErrorMessages.OPENAI_CLIENT_REQUIRED)
            
    def _create_chat_completion(
        self, 
        messages: List[Dict[str, Any]], 
        max_tokens: int = AIConfig.MAX_TOKENS,
        temperature: float = AIConfig.TEMPERATURE,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """OpenAI Chat Completion API 호출"""
        try:
            completion_kwargs = {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            
            if response_format:
                completion_kwargs["response_format"] = response_format
            
            response = self.client.chat.completions.create(**completion_kwargs)
            
            completion_content = response.choices[0].message.content
            return completion_content.strip() if completion_content else None
            
        except Exception as e:
            self.logger.exception(f"OpenAI API 호출 중 오류 발생: {e}")
            return None 