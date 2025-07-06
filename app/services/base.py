import logging
from abc import ABC, abstractmethod
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


class BaseService(ABC):
    """모든 서비스 클래스의 기본 클래스"""
    
    def __init__(self, openai_client: Optional[OpenAI] = None, model_name: str = "gpt-4o-mini"):
        self.client = openai_client or OpenAI()
        self.model_name = model_name
        self.logger = logger


class BaseAIService(BaseService):
    """OpenAI를 사용하는 서비스들의 기본 클래스"""
    
    def __init__(self, openai_client: Optional[OpenAI] = None, model_name: str = "gpt-4o-mini"):
        super().__init__(openai_client, model_name)
        if not self.client:
            raise ValueError("OpenAI client is required for AI services") 