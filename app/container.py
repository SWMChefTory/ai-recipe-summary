
from dotenv import load_dotenv
from google import genai

load_dotenv()

from dependency_injector import containers, providers

from app.prompts import prompt_path, tool_path
from app.briefing.client import BriefingClient
from app.briefing.generator import BriefingGenerator
from app.briefing.service import BriefingService
from app.meta.client import MetaClient
from app.meta.extractor import MetaExtractor
from app.meta.service import MetaService
from app.step.generator import StepGenerator
from app.step.service import StepService
from app.scene.generator import SceneGenerator
from app.scene.service import SceneService
from app.verify.service import VerifyService
from app.verify.generator import VerifyGenerator


class Container(containers.DeclarativeContainer):
    """의존성 주입 컨테이너"""

    # Configuration
    wiring_config = containers.WiringConfiguration(
        packages=[
            "app.meta",
            "app.step",
            "app.briefing",
            "app.scene",
            "app.verify",
        ]
    )
    config = providers.Configuration()
    config.google.api_key.from_env("GOOGLE_API_KEY")

    # Gemini - Client 설정 (Vertex AI)
    config.google.vertex.project.from_env("VERTEX_AI_PROJECT_ID")

    genai_client = providers.Singleton(
        genai.Client,
        vertexai=True,
        project=config.google.vertex.project,
        location="global",
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
        model="gemini-2.5-pro",
        # Fallbacks must be GA models. Preview fallbacks share system-limit
        # throttling with primary and may also reject thinking_level (Gemini
        # 2.5 vs 3 incompatibility), causing user-visible 500s. See incident
        # 2026-04 (scene endpoint thinking_level bug).
        fallback_model="gemini-2.5-flash",
        secondary_fallback_model="gemini-2.5-flash-lite",

        extract_ingredient_prompt_path=providers.Callable(prompt_path, "meta.extract_ingredient"),
        extract_ingredient_tool_path=providers.Callable(tool_path, "meta.extract_ingredient"),

        video_extract_prompt_path=providers.Callable(prompt_path, "meta.video_extract"),
        video_extract_tool_path=providers.Callable(tool_path, "meta.video_meta"),
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
        model="gemini-2.5-pro",
        # Same policy as meta: GA-only fallback chain.
        fallback_model="gemini-2.5-flash",
        secondary_fallback_model="gemini-2.5-flash-lite",
        video_step_tool_path=providers.Callable(tool_path, "step.video_step"),
        video_summarize_user_prompt_path=providers.Callable(prompt_path, "step.video_summarize"),
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
        model="gemini-3.1-flash-lite-preview",
        fallback_model="gemini-2.5-flash-lite",
        generate_user_prompt_path=providers.Callable(prompt_path, "briefing.user_prompt"),
        generate_tool_path=providers.Callable(tool_path, "briefing.emit_briefing"),
    )
    briefing_service = providers.Factory(
        BriefingService,
        client=briefing_client,
        generator=briefing_generator,
    )

    # Scene
    scene_generator = providers.Singleton(
        SceneGenerator,
        client=genai_client,
        model="gemini-3-flash-preview",
        # GA fallback (was: gemini-2.5-flash-lite). preview primary may hit
        # system-limit throttling; fallback must be GA to recover. Uses
        # video_scene_conf_fallback (no thinking_level) for Gemini 2.5 compat.
        fallback_model="gemini-2.5-flash",
        video_scene_tool_path=providers.Callable(tool_path, "scene.video_scene"),
        video_scene_user_prompt_path=providers.Callable(prompt_path, "scene.video_scene"),
    )
    scene_service = providers.Factory(
        SceneService,
        generator=scene_generator,
    )

    # Verify
    verify_generator = providers.Singleton(
        VerifyGenerator,
        client=genai_client,
        model="gemini-3.1-flash-lite-preview",
        fallback_model="gemini-2.5-flash-lite",
        verify_user_prompt_path=providers.Callable(prompt_path, "verify.verify"),
        verify_tool_path=providers.Callable(tool_path, "verify.verify"),
    )

    verify_service = providers.Factory(
        VerifyService,
        generator=verify_generator,
    )


# 전역 컨테이너 인스턴스
container = Container()
