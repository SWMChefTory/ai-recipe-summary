from dotenv import load_dotenv

load_dotenv()

from pathlib import Path

from dependency_injector import containers, providers
from openai import AsyncOpenAI

from app.briefing.client import BriefingClient
from app.briefing.generator import BriefingGenerator
from app.briefing.service import BriefingService
from app.caption.client import CaptionClient
from app.caption.recipe_validator import CaptionRecipeValidator
from app.caption.service import CaptionService
from app.meta.client import MetaClient
from app.meta.extractor import MetaExtractor
from app.meta.service import MetaService
from app.step.generator import StepGenerator
from app.step.service import StepService
from app.vision.client import VisionClient
from app.vision.extractor import VisionExtractor
from app.vision.generator import VisionGenerator
from app.vision.service import VisionService


class Container(containers.DeclarativeContainer):
    """의존성 주입 컨테이너"""

    # Configuration
    wiring_config = containers.WiringConfiguration(
        packages=[
            "app.caption",
            "app.meta",
            "app.step",
            "app.briefing",
        ]
    )
    config = providers.Configuration()
    config.openai.api_key.from_env("OPENAI_API_KEY")
    config.google.api_key.from_env("GOOGLE_API_KEY")

    config.aws.access_key.from_env("AWS_ACCESS_KEY_ID")
    config.aws.secret_key.from_env("AWS_SECRET_ACCESS_KEY")
    config.aws.region.from_env("AWS_REGION")

    config.bedrock.model_id.from_env("BEDROCK_MODEL_ID")
    config.bedrock.profile.from_env("BEDROCK_INFERENCE_PROFILE_ARN")

    openai_client = providers.Singleton(
        AsyncOpenAI,
        api_key=config.openai.api_key,
        timeout=20.0,
    )

    # Caption
    caption_client = providers.Singleton(CaptionClient)
    recipe_validator = providers.Singleton(
        CaptionRecipeValidator,
        openai_client=openai_client,
    )
    caption_service = providers.Factory(
        CaptionService,
        client=caption_client,
        recipe_validator=recipe_validator,
    )

    # Meta
    meta_client = providers.Singleton(
        MetaClient,
        api_key=config.google.api_key,
        timeout=20.0,
    )
    meta_extractor = providers.Singleton(
        MetaExtractor,
        model_id=config.bedrock.model_id,
        region=config.aws.region,
        inference_profile_arn=config.bedrock.profile,

        extract_prompt_path=Path("app/meta/prompt/user/extract.md"),
        extract_tool_path=Path("app/meta/prompt/tool/extract.json"),

        extract_ingredient_prompt_path=Path("app/meta/prompt/user/extract_ingredient.md"),
        extract_ingredient_tool_path=Path("app/meta/prompt/tool/extract_ingredient.json"),
    )
    meta_service = providers.Factory(
        MetaService,
        extractor=meta_extractor,
        client=meta_client,
    )

    # Summary
    step_generator = providers.Singleton(
        StepGenerator,
        model_id=config.bedrock.model_id,
        region=config.aws.region,
        inference_profile_arn=config.bedrock.profile,

        step_tool_path=Path("app/step/prompt/tool/step.json"),
        summarize_user_prompt_path=Path("app/step/prompt/user/summarize.md"),
        merge_user_prompt_path=Path("app/step/prompt/user/merge.md"),
    )
    step_service = providers.Factory(
        StepService,
        generator=step_generator,
    )

    # Briefing
    briefing_client = providers.Singleton(
        BriefingClient,
        api_key=config.google.api_key,
        timeout=20.0,
    )
    briefing_generator = providers.Singleton(
        BriefingGenerator,
        model_id=config.bedrock.model_id,
        region=config.aws.region,
        inference_profile_arn=config.bedrock.profile,
        max_tokens=2048,

        filter_user_prompt_path=Path("app/briefing/prompt/filter/user_prompt.md"),
        filter_tool_path=Path("app/briefing/prompt/filter/emit_comment.json"),

        generate_user_prompt_path=Path("app/briefing/prompt/generator/user_prompt.md"),
        generate_tool_path=Path("app/briefing/prompt/generator/emit_briefing.json"),
    )
    briefing_service = providers.Factory(
        BriefingService,
        client=briefing_client,
        generator=briefing_generator,
    )


# 전역 컨테이너 인스턴스
container = Container()
