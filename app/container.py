from dotenv import load_dotenv

load_dotenv()

from pathlib import Path

from dependency_injector import containers, providers
from openai import AsyncOpenAI

from app.caption.client import CaptionClient
from app.caption.recipe_validator import CaptionRecipeValidator
from app.caption.service import CaptionService
from app.ingredient.client import IngredientClient
from app.ingredient.extractor import IngredientExtractor
from app.ingredient.service import IngredientService


class Container(containers.DeclarativeContainer):
    """의존성 주입 컨테이너"""

    # Configuration
    wiring_config = containers.WiringConfiguration(
        packages=[
            "app.caption",
            "app.ingredient",
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

    caption_client = providers.Factory(CaptionClient)
    recipe_validator = providers.Factory(
        CaptionRecipeValidator,
        openai_client=openai_client,
    )
    caption_service = providers.Factory(
        CaptionService,
        client=caption_client,
        recipe_validator=recipe_validator,
    )

    ingredient_client = providers.Factory(
        IngredientClient,
        api_key=config.google.api_key,
        timeout=20.0,
    )
    ingredient_extractor = providers.Factory(
        IngredientExtractor,
        model_id=config.bedrock.model_id,
        region=config.aws.region,
        inference_profile_arn=config.bedrock.profile,
        system_path=Path("app/ingredient/prompt/system.md"),
        description_user_path=Path("app/ingredient/prompt/description_user.md"),
        caption_user_path=Path("app/ingredient/prompt/caption_user.md"),
    )
    ingredient_service = providers.Factory(
        IngredientService,
        extractor=ingredient_extractor,
        client=ingredient_client,
    )


# 전역 컨테이너 인스턴스
container = Container()
