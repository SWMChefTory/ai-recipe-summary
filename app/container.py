
from dotenv import load_dotenv
from google import genai

load_dotenv()

from pathlib import Path

from dependency_injector import containers, providers

from app.briefing.client import BriefingClient
from app.briefing.generator import BriefingGenerator
from app.briefing.service import BriefingService
from app.meta.client import MetaClient
from app.meta.extractor import MetaExtractor
from app.meta.service import MetaService
from app.step.generator import StepGenerator
from app.step.service import StepService
from app.verify.service import VerifyService
from app.verify.client import VerifyClient
from app.verify.generator import VerifyGenerator

def _resolve_caption_upload_urls(raw_urls: str):
    return [url.strip() for url in (raw_urls or "").split(",") if url.strip()]


class Container(containers.DeclarativeContainer):
    """의존성 주입 컨테이너"""

    # Configuration
    wiring_config = containers.WiringConfiguration(
        packages=[
            "app.meta",
            "app.step",
            "app.briefing",
            "app.verify",
        ]
    )
    config = providers.Configuration()
    config.google.api_key.from_env("GOOGLE_API_KEY")
    config.google.ai_api_key.from_env("GOOGLE_AI_API_KEY")

    config.google.gemini.model_id.from_env("GEMINI_MODEL_ID")
    config.google.gemini.model_id_lite.from_env("GEMINI_MODEL_ID_LITE")
    config.google.gemini.fallback_model_id.from_env(
        "GEMINI_FALLBACK_MODEL_ID",
        default="gemini-3.0-flash",
    )
    config.cloud_run.caption_urls.from_env(
        "CLOUD_RUN_CAPTION_URLS",
        default="",
    )
    config.cloud_run.request_timeout_seconds.from_value(300)

    # Gemini - Client 설정
    genai_client = providers.Singleton(
        genai.Client,
        api_key=config.google.ai_api_key,
    )

    # Meta
    meta_client = providers.Singleton(
        MetaClient,
        api_key=config.google.api_key,
        timeout=20.0,
    )
    meta_extractor = providers.Singleton(
        MetaExtractor,
        client=genai_client,
        model=config.google.gemini.model_id,
        fallback_model=config.google.gemini.fallback_model_id,

        extract_ingredient_prompt_path=Path("app/meta/prompt/user/extract_ingredient.md"),
        extract_ingredient_tool_path=Path("app/meta/prompt/tool/extract_ingredient.json"),

        video_extract_prompt_path=Path("app/meta/prompt/user/video_extract.md"),
        video_extract_tool_path=Path("app/meta/prompt/tool/video_meta.json"),
    )
    meta_service = providers.Factory(
        MetaService,
        extractor=meta_extractor,
        client=meta_client,
    )

    # Summary
    step_generator = providers.Singleton(
        StepGenerator,
        client=genai_client,
        model=config.google.gemini.model_id,
        fallback_model=config.google.gemini.fallback_model_id,
        video_step_tool_path=Path("app/step/prompt/tool/video_step.json"),
        video_summarize_user_prompt_path=Path("app/step/prompt/user/video_summarize.md"),
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
        client=genai_client,
        model=config.google.gemini.model_id_lite,
        fallback_model=config.google.gemini.fallback_model_id,
        generate_user_prompt_path=Path("app/briefing/prompt/generator/user_prompt.md"),
        generate_tool_path=Path("app/briefing/prompt/generator/emit_briefing.json"),
    )
    briefing_service = providers.Factory(
        BriefingService,
        client=briefing_client,
        generator=briefing_generator,
    )

    # Verify
    verify_client = providers.Singleton(
        VerifyClient,
        upload_service_urls=providers.Callable(
            _resolve_caption_upload_urls,
            config.cloud_run.caption_urls,
        ),
        request_timeout_seconds=config.cloud_run.request_timeout_seconds,
    )

    verify_generator = providers.Singleton(
        VerifyGenerator,
        client=genai_client,
        model=config.google.gemini.model_id_lite,
        fallback_model=config.google.gemini.fallback_model_id,
        verify_user_prompt_path=Path("app/verify/prompt/user/verify.md"),
        verify_tool_path=Path("app/verify/prompt/tool/verify.json"),
    )

    verify_service = providers.Factory(
        VerifyService,
        client=verify_client,
        generator=verify_generator,
        genai_client=genai_client, # genai_client 주입 추가
    )


# 전역 컨테이너 인스턴스
container = Container()
