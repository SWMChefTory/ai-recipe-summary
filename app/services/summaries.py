import json
import os
from typing import List, Optional

import boto3
from botocore.config import Config
from openai import OpenAI

from app.constants import AIConfig, ErrorMessages
from app.models.captions import CaptionResponse
from app.models.ingredients import Ingredient
from app.models.summaries import CookingProcessSummary
from app.services.base import BaseAIService, TemplateService


class SummariesService(BaseAIService):
    """조리 단계 요약 생성 서비스 - Bedrock Claude Sonnet 4"""

    def __init__(
        self,
        openai_client: Optional[OpenAI] = None,
        model_name: Optional[str] = None,      
        bedrock_model_id: Optional[str] = None,
        aws_region: Optional[str] = None,
        inference_profile_arn: Optional[str] = None,
    ):
        super().__init__(openai_client, model_name or AIConfig.DEFAULT_MODEL)

        self.aws_region = aws_region or os.getenv("AWS_REGION", "ap-northeast-2")
        self.inference_profile_arn = inference_profile_arn or os.getenv("BEDROCK_INFERENCE_PROFILE_ARN")
        self.bedrock_model_id = bedrock_model_id or os.getenv(
            "BEDROCK_MODEL_ID",
            "anthropic.claude-sonnet-4-20250514-v1:0",
        )

        self._bedrock_rt = boto3.client(
            "bedrock-runtime",
            region_name=self.aws_region,
            config=Config(read_timeout=3600, connect_timeout=10, retries={"max_attempts": 3}),
        )

    async def create_summary(
        self,
        video_id: str,
        video_type: str,
        caption_response: CaptionResponse,
        ingredients: List[Ingredient],
    ) -> Optional[CookingProcessSummary]:
        try:
            ai_response = self._generate_ai_summary(caption_response, ingredients)
            if not ai_response:
                return None

            summary_data = json.loads(ai_response)
            return CookingProcessSummary(
                description=summary_data.get("description", ""),
                steps=summary_data.get("steps", []),
            )
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 파싱 오류: {e}")
            return None
        except Exception as e:
            self.logger.exception(f"조리 단계 요약 생성 중 오류: {e}")
            return None

    def _generate_ai_summary(
        self,
        caption_response: CaptionResponse,
        ingredients: List[Ingredient],
    ) -> Optional[str]:
        try:
            system_prompt = TemplateService.load_system_prompt("summaries.md")
            user_prompt = self._create_user_prompt(caption_response, ingredients)

            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
                ],
                "max_tokens": 16000,
                "temperature": 0,
            }

            target_model_id = (
                self.inference_profile_arn or self.bedrock_model_id
            )

            resp = self._bedrock_rt.invoke_model(
                modelId=target_model_id,
                accept="application/json",
                contentType="application/json",
                body=json.dumps(body).encode("utf-8"),
            )

            raw = resp.get("body")
            raw_bytes = raw.read() if hasattr(raw, "read") else (raw or b"")
            if not raw_bytes:
                self.logger.error("Bedrock 응답이 비어 있습니다.")
                return ErrorMessages.SUMMARY_FAILED

            text = self._extract_text_from_bedrock_response(raw_bytes)
            return text or ErrorMessages.SUMMARY_EMPTY

        except Exception as e:
            self.logger.exception(
                "AI 요약 생성 중 오류: %s (프로필 ARN/리전/IAM 권한을 확인하세요.)", e
            )
            return ErrorMessages.SUMMARY_FAILED

    def _extract_text_from_bedrock_response(self, body_bytes: bytes) -> str:
        payload_raw = body_bytes.decode("utf-8") if body_bytes else ""
        if not payload_raw:
            return ""
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            return payload_raw

        contents = payload.get("content", [])
        for c in contents:
            if c.get("type") == "text" and "text" in c:
                return c["text"]
        return json.dumps(payload, ensure_ascii=False)

    def _create_user_prompt(
        self,
        caption_response: CaptionResponse,
        ingredients: List[Ingredient],
    ) -> str:
        template = self.template_env.get_template("summaries.jinja2")
        return template.render(
            captions=caption_response.captions,
            lang_code=caption_response.lang_code,
            ingredients=ingredients,
        )