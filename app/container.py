
from dotenv import load_dotenv
from google import genai

from app.briefing.comment_classifier import CommentClassifier

load_dotenv()

from pathlib import Path

from dependency_injector import containers, providers

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
from app.verify.service import VerifyService
from app.verify.client import VerifyClient
from app.verify.generator import VerifyGenerator


class Container(containers.DeclarativeContainer):
    """의존성 주입 컨테이너"""

    # Configuration
    wiring_config = containers.WiringConfiguration(
        packages=[
            "app.caption",
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

    config.aws.access_key.from_env("AWS_ACCESS_KEY_ID")
    config.aws.secret_key.from_env("AWS_SECRET_ACCESS_KEY")
    config.aws.region.from_env("AWS_REGION")

    config.aws_lambda.function_url_seoul.from_env("AWS_LAMBDA_FUNCTION_URL_SEOUL")
    config.aws_lambda.function_url_seoul_no_cookie.from_env("AWS_LAMBDA_FUNCTION_URL_SEOUL_NO_COOKIE")
    config.aws_lambda.function_url_seoul_no_cookie_2.from_env("AWS_LAMBDA_FUNCTION_URL_SEOUL_NO_COOKIE_2")
    config.aws_lambda.function_url_seoul_no_cookie_3.from_env("AWS_LAMBDA_FUNCTION_URL_SEOUL_NO_COOKIE_3")
    config.aws_lambda.function_url_seoul_no_cookie_4.from_env("AWS_LAMBDA_FUNCTION_URL_SEOUL_NO_COOKIE_4")
    config.aws_lambda.function_url_seoul_no_cookie_5.from_env("AWS_LAMBDA_FUNCTION_URL_SEOUL_NO_COOKIE_5")
    config.aws_lambda.function_url_seoul_no_cookie_6.from_env("AWS_LAMBDA_FUNCTION_URL_SEOUL_NO_COOKIE_6")
    config.aws_lambda.function_url_seoul_no_cookie_7.from_env("AWS_LAMBDA_FUNCTION_URL_SEOUL_NO_COOKIE_7")
    config.aws_lambda.function_url_seoul_no_cookie_8.from_env("AWS_LAMBDA_FUNCTION_URL_SEOUL_NO_COOKIE_8")
    config.aws_lambda.function_url_tokyo.from_env("AWS_LAMBDA_FUNCTION_URL_TOKYO")
    config.aws_lambda.function_url_osaka.from_env("AWS_LAMBDA_FUNCTION_URL_OSAKA")
    config.aws_lambda.function_url_singapore.from_env("AWS_LAMBDA_FUNCTION_URL_SINGAPORE")
    config.aws_lambda.function_url_oregon.from_env("AWS_LAMBDA_FUNCTION_URL_OREGON")
    config.aws_lambda.function_url_virginia.from_env("AWS_LAMBDA_FUNCTION_URL_VIRGINIA")

    # Gemini - Client 설정
    genai_client = providers.Singleton(
        genai.Client,
        api_key=config.google.ai_api_key,
    )

    # Caption
    caption_client = providers.Singleton(
      CaptionClient,
      region=config.aws.region,
      aws_lambda_function_urls=providers.List(
          config.aws_lambda.function_url_seoul, 
          config.aws_lambda.function_url_seoul_no_cookie,
          config.aws_lambda.function_url_seoul_no_cookie_2,
          config.aws_lambda.function_url_seoul_no_cookie_3,
          config.aws_lambda.function_url_seoul_no_cookie_4,
          config.aws_lambda.function_url_seoul_no_cookie_5,
          config.aws_lambda.function_url_seoul_no_cookie_6,
          config.aws_lambda.function_url_seoul_no_cookie_7,
          config.aws_lambda.function_url_seoul_no_cookie_8,
          config.aws_lambda.function_url_tokyo,
          config.aws_lambda.function_url_osaka,
          config.aws_lambda.function_url_singapore,
          config.aws_lambda.function_url_oregon,
          config.aws_lambda.function_url_virginia,
      ),
      aws_access_key_id=config.aws.access_key,
      aws_secret_access_key=config.aws.secret_key,
    )
    recipe_validator = providers.Singleton(
        CaptionRecipeValidator,
        client=genai_client,
        model=config.google.gemini.model_id,
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
        client=genai_client,
        model=config.google.gemini.model_id,

        extract_prompt_path=Path("app/meta/prompt/user/extract.md"),
        extract_tool_path=Path("app/meta/prompt/tool/extract.json"),

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
        step_tool_path=Path("app/step/prompt/tool/step.json"),
        summarize_user_prompt_path=Path("app/step/prompt/user/summarize.md"),
        merge_user_prompt_path=Path("app/step/prompt/user/merge.md"),
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
        model=config.google.gemini.model_id,
        generate_user_prompt_path=Path("app/briefing/prompt/generator/user_prompt.md"),
        generate_tool_path=Path("app/briefing/prompt/generator/emit_briefing.json"),
    )
    comment_classifier = providers.Singleton(
        CommentClassifier,
        model_id = "NamYunje/recipe-comment-classifier"
    )
    
    briefing_service = providers.Factory(
        BriefingService,
        client=briefing_client,
        generator=briefing_generator,
        classifier=comment_classifier
    )

    # Verify
    verify_client = providers.Singleton(
        VerifyClient,
        region=config.aws.region,
        aws_lambda_function_urls=providers.List(
            config.aws_lambda.function_url_seoul,
            config.aws_lambda.function_url_seoul_no_cookie,
            config.aws_lambda.function_url_seoul_no_cookie_2,
            config.aws_lambda.function_url_seoul_no_cookie_3,
            config.aws_lambda.function_url_seoul_no_cookie_4,
            config.aws_lambda.function_url_seoul_no_cookie_5,
            config.aws_lambda.function_url_seoul_no_cookie_6,
            config.aws_lambda.function_url_seoul_no_cookie_7,
            config.aws_lambda.function_url_seoul_no_cookie_8,
            config.aws_lambda.function_url_tokyo,
            config.aws_lambda.function_url_osaka,
            config.aws_lambda.function_url_singapore,
            config.aws_lambda.function_url_oregon,
            config.aws_lambda.function_url_virginia,
        ),
        aws_access_key_id=config.aws.access_key,
        aws_secret_access_key=config.aws.secret_key,
    )

    verify_generator = providers.Singleton(
        VerifyGenerator,
        client=genai_client,
        model=config.google.gemini.model_id,
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
