import os

from dependency_injector import containers, providers
from openai import OpenAI

from app.services.audio import AudioService
from app.services.audio_extractor import AudioExtractor
from app.services.caption_extractor import CaptionExtractor
from app.services.captions import CaptionService
from app.services.ingredients import IngredientsService
from app.services.summaries import SummariesService
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
    model_name = providers.Object("gpt-4o")
    google_api_key = providers.Object(os.getenv("GOOGLE_API_KEY"))

    # Services
    audio_service = providers.Factory(
        AudioService,
        openai_client=openai_client,
        model_name=model_name,
    )
    
    caption_extractor = providers.Factory(
        CaptionExtractor,
    )
    
    audio_extractor = providers.Factory(
        AudioExtractor,
    )
    
    youtube_service = providers.Factory(
        YouTubeService,
        google_api_key=google_api_key,
        audio_service=audio_service,
        caption_extractor=caption_extractor,
        audio_extractor=audio_extractor,
    )

    caption_service = providers.Factory(
        CaptionService,
    )

    ingredients_service = providers.Factory(
        IngredientsService,
        openai_client=openai_client,
        model_name=model_name,
    )

    summaries_service = providers.Factory(
        SummariesService,
        openai_client=openai_client,
        model_name=model_name,
    )


# 전역 컨테이너 인스턴스
container = Container()
