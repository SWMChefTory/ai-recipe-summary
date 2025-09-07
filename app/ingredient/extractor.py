# app/ingredient/extractor.py
import json
from pathlib import Path
from typing import Dict, List

import boto3
from botocore.config import Config


class IngredientExtractor:
    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        inference_profile_arn: str,
        system_path: Path,
        description_user_path: Path,
        caption_user_path: Path,
    ):
        self.model_id = model_id
        self.region = region
        self.inference_profile_arn = inference_profile_arn
        
        # 프롬프트 로드
        self.system_prompt = system_path.read_text(encoding='utf-8')
        self.description_user_prompt = description_user_path.read_text(encoding='utf-8')
        self.caption_user_prompt = caption_user_path.read_text(encoding='utf-8')
        
        # Bedrock 클라이언트 초기화
        config = Config(
            region_name=region,
            retries={'max_attempts': 3, 'mode': 'adaptive'}
        )
        self.client = boto3.client('bedrock-runtime', config=config)

    def _call_bedrock(self, user_prompt: str) -> str:
        """Bedrock Claude Sonnet 4를 호출하여 응답을 받는다."""
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "system": self.system_prompt,
            "max_tokens": 1024,
            "temperature": 0,
            "messages": [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
        }
        
        # inference profile을 사용하는 경우 모델 ID 대신 profile ARN 사용
        model_identifier = self.inference_profile_arn if self.inference_profile_arn else self.model_id
        
        resp = self.client.invoke_model(
            modelId=model_identifier,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload),
        )
        body = json.loads(resp["body"].read())
        return body["content"][0]["text"]

    def extract_from_description(self, description: str) -> List[Dict]:
        """유튜브 동영상 설명란에서 재료를 추출한다."""
        prompt = self.description_user_prompt.replace("{{ description }}", description)
        return json.loads(self._call_bedrock(prompt))

    def extract_from_captions(self, captions: str, lang_code: str) -> List[Dict]:
        """자막에서 재료를 추출한다."""
        prompt = (self.caption_user_prompt
                  .replace("{{ captions }}", captions)
                  .replace("{{ lang_code }}", lang_code))
        return json.loads(self._call_bedrock(prompt))