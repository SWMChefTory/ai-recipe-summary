from tokenize import Comment

from dotenv import load_dotenv

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
    config.google.api_key.from_env("GOOGLE_API_KEY")

    config.aws.access_key.from_env("AWS_ACCESS_KEY_ID")
    config.aws.secret_key.from_env("AWS_SECRET_ACCESS_KEY")
    config.aws.region.from_env("AWS_REGION")

    config.bedrock.model_id.from_env("BEDROCK_MODEL_ID")
    config.bedrock.profile.from_env("BEDROCK_INFERENCE_PROFILE_ARN")

    config.aws_lambda.function_url_seoul.from_env("AWS_LAMBDA_FUNCTION_URL_SEOUL")
    config.aws_lambda.function_url_tokyo.from_env("AWS_LAMBDA_FUNCTION_URL_TOKYO")
    config.aws_lambda.function_url_osaka.from_env("AWS_LAMBDA_FUNCTION_URL_OSAKA")
    config.aws_lambda.function_url_singapore.from_env("AWS_LAMBDA_FUNCTION_URL_SINGAPORE")
    config.aws_lambda.function_url_oregon.from_env("AWS_LAMBDA_FUNCTION_URL_OREGON")
    config.aws_lambda.function_url_virginia.from_env("AWS_LAMBDA_FUNCTION_URL_VIRGINIA")

    # Caption
    caption_client = providers.Singleton(
      CaptionClient,
      region=config.aws.region,
      aws_lambda_function_urls=providers.List(
          config.aws_lambda.function_url_seoul, 
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
        model_id=config.bedrock.model_id,
        region=config.aws.region,
        inference_profile_arn=config.bedrock.profile,
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


# 전역 컨테이너 인스턴스
container = Container()
