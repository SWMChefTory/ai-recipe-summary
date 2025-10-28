import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

import boto3
from botocore.config import Config

from app.briefing.exception import BriefingErrorCode, BriefingException


class IBriefingGenerator(ABC):
    """레시피 관련 댓글 필터링 및 브리핑 생성을 담당하는 인터페이스"""

    @abstractmethod
    def filter_comments(self, comments: List[str]) -> List[str]:
        """
        댓글(List[str])을 입력받아 레시피 관련 댓글만 반환.
        """
        pass

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
        model_id: str,
        region: str,
        inference_profile_arn: str,
        max_tokens: int,
        temperature: float = 0.0,
        generate_user_prompt_path: Path,
        generate_tool_path: Path,
        filter_user_prompt_path: Path,
        filter_tool_path: Path,
    ):
        self.logger = logging.getLogger(__name__)
        self.model_id = model_id
        self.region = region
        self.inference_profile_arn = inference_profile_arn
        self.max_tokens = max_tokens
        self.temperature = temperature

        # ---- 프롬프트/툴 로드 ----
        self.filter_prompt = filter_user_prompt_path.read_text(encoding="utf-8")
        self.filter_tool = json.loads(filter_tool_path.read_text(encoding="utf-8"))

        self.briefing_prompt = generate_user_prompt_path.read_text(encoding="utf-8")
        self.briefing_tool = json.loads(generate_tool_path.read_text(encoding="utf-8"))

        self.client = boto3.client(
            "bedrock-runtime",
            config=Config(
                region_name=region,
                retries={"max_attempts": 3, "mode": "adaptive"},
                connect_timeout=10,
                read_timeout=180,
            ),
        )

    def __converse_briefing(self, user_prompt: str, tool: List[dict]) -> List[str]:
        try:
            model_identifier = self.inference_profile_arn or self.model_id
            tool_name = tool[0].get("toolSpec", {}).get("name")
        
            resp = self.client.converse(
                modelId=model_identifier,
                system=[{"text": "You must call the provided tool only. Do not produce free-form text. All natural-language must be Korean. Use proper UTF-8 encoding for all Korean characters. Ensure complete Unicode characters, especially for Korean syllables like 좋, 않, 됐, etc."}],
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                toolConfig={"tools": tool, "toolChoice": {"tool": {"name": tool_name}}},
                inferenceConfig={"maxTokens": self.max_tokens, "temperature": self.temperature},
            )
            content = resp["output"]["message"]["content"]

            for item in content:
                tu = item.get("toolUse")
                if tu and tu.get("name") == tool_name:
                    obj = tu.get("input", {})
                    items = obj.get("items", [])
                    return [str(item) for item in items]

        except Exception as e:
            self.logger.error(f"LLM 호출 중 오류가 발생했습니다: {e}")
            raise

    def filter_comments(self, comments: List[str]) -> List[str]:
        """
        댓글(List[str])을 입력받아 레시피 관련 댓글만 반환.
        """
        try:
            comments_json = json.dumps(
                [c for c in comments if isinstance(c, str) and c.strip()],
                ensure_ascii=False
            )
            prompt = self.filter_prompt.replace("{{ comments_json }}", comments_json)
            return self.__converse_briefing(prompt, self.filter_tool)

        except Exception as e:
            self.logger.error(f'댓글 필터링 중 오류가 발생했습니다: {e}')
            raise BriefingException(BriefingErrorCode.BRIEFING_GENERATE_FAILED)

    def generate(self, comments: List[str]) -> List[str]:
        """
        댓글(List[str])을 입력받아 브리핑 문장 리스트를 반환.
        - 레시피 관련 2~5문장
        - 2개 미만이면 빈 리스트 반환
        """
        try:
            comments_json = json.dumps(
                [c for c in comments if isinstance(c, str) and c.strip()],
                ensure_ascii=False
            )
            prompt = self.briefing_prompt.replace("{{ comments_json }}", comments_json)
            result = self.__converse_briefing(prompt, self.briefing_tool)

            if len(result) > 4:
                result = result[:4]

            if len(result) < 2:
                return []

            return result

        except Exception as e:
            self.logger.error(f'브리핑 생성 중 오류가 발생했습니다: {e}')
            raise BriefingException(BriefingErrorCode.BRIEFING_GENERATE_FAILED)
