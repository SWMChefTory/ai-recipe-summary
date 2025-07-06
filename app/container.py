import os

from dependency_injector import containers, providers
from openai import OpenAI

from app.services.audio import AudioService
from app.services.captions import CaptionService
from app.services.ingredients import IngredientsService
from app.services.recipe import RecipeService
from app.services.summaries import SummaryService
from app.services.youtube import YouTubeService


class Container(containers.DeclarativeContainer):
    """의존성 주입 컨테이너"""

    # Configuration
    wiring_config = containers.WiringConfiguration(
        packages=[
            "app.api",
            "app.services",
        ]
    )

    # External dependencies
    openai_client = providers.Singleton(OpenAI)
    
    # Configuration values
    model_name = providers.Object("gpt-4o-mini")
    google_api_key = providers.Object(os.getenv("GOOGLE_API_KEY"))

    # Services
    audio_service = providers.Factory(
        AudioService,
        openai_client=openai_client,
        model_name=model_name,
    )
    
    youtube_service = providers.Factory(
        YouTubeService,
        google_api_key=google_api_key,
        audio_service=audio_service,
    )

    caption_service = providers.Factory(
        CaptionService,
    )

    ingredients_service = providers.Factory(
        IngredientsService,
        openai_client=openai_client,
        model_name=model_name,
    )

    summary_service = providers.Factory(
        SummaryService,
        openai_client=openai_client,
        model_name=model_name,
    )

    recipe_service = providers.Factory(
        RecipeService,
        youtube_service=youtube_service,
        caption_service=caption_service,
        ingredients_service=ingredients_service,
        summary_service=summary_service,
    )


# 전역 컨테이너 인스턴스
container = Container()
