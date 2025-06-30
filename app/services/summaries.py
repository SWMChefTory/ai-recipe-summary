import logging
from importlib import resources
from typing import Dict, List

import jinja2
from openai import OpenAI

logger = logging.getLogger(__name__)
MODEL_NAME = "gpt-4o-mini"

client = OpenAI()

def load_template(name: str) -> str:
    return resources.files("app.prompts.user").joinpath(name).read_text()

env = jinja2.Environment(loader=jinja2.FunctionLoader(load_template), autoescape=False)

def summarize(subtitles: List[Dict], description: str, client: OpenAI = client) -> str:
    try:
        tpl = env.get_template("recipe.jinja2")
        system_prompt = resources.files("app.prompts.system").joinpath("recipe.txt").read_text()
        user_prompt = tpl.render(subtitles=subtitles, description=description)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=4096,
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        result = response.choices[0].message.content.strip()
        return result if result else "[요약 결과가 비어 있습니다]"

    except Exception as e:
        logger.exception("요약 생성 중 오류 발생")
        return "[요약 실패: 문제가 발생했습니다]"
