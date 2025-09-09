import json
import logging
from pathlib import Path

from openai import AsyncOpenAI

from app.caption.exception import CaptionErrorCode, CaptionException


class CaptionRecipeValidator:
    def __init__(self, openai_client: AsyncOpenAI):
        self.logger = logging.getLogger(__name__)
        self.client = openai_client

        base = Path(__file__).parent / "prompt"
        self.template = (base / "recipe_detect.md").read_text(encoding="utf-8")
        self.tools = json.loads((base / "emit_bit_tool.json").read_text(encoding="utf-8"))

    async def validate(self, captions: str, lang_code: str):
        try:
            # 1) 프롬프트 채우기
            prompt = (
                self.template.replace("{{ lang_code }}", lang_code)
                        .replace("{{ captions }}", captions)
            )

            # 2) 호출: tool_choice로 emit_bit 강제
            resp = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                tools=self.tools,
                tool_choice={"type": "function", "function": {"name": "emit_bit"}},
                temperature=0,
            )

            # 3) 툴 콜 파싱
            choice = resp.choices[0].message
            bit = None

            if getattr(choice, "tool_calls", None):
                call = choice.tool_calls[0]
                args = json.loads(call.function.arguments or "{}")
                bit = args.get("bit")

            # 4) 검증
            if bit not in (0, 1):
                raise CaptionException(CaptionErrorCode.CAPTION_VALIDATE_FAILED)

            if bit != 1:
                raise CaptionException(CaptionErrorCode.CAPTION_NOT_RECIPE)

        except CaptionException:
            raise
          
        except Exception as e:
            self.logger.exception(e)
            raise CaptionException(CaptionErrorCode.CAPTION_VALIDATE_FAILED)