from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Header

from app.container import Container
from app.enum import LanguageType
from app.scene.schema import SceneResponse, VideoSceneRequest
from app.scene.service import SceneService

router = APIRouter()


@router.post("/scenes/video", response_model=SceneResponse)
@inject
async def generate_scenes_by_video(
    request: VideoSceneRequest,
    x_country_code: Annotated[str | None, Header(alias="X-Country-Code")] = None,
    scene_service: SceneService = Depends(Provide[Container.scene_service]),
):
    country = (x_country_code or "").strip().upper()
    language = LanguageType.KR if country == "KR" else LanguageType.EN

    # step 번호(1-based) → step_id 매핑 테이블
    step_number_to_id = {
        i + 1: s.step_id for i, s in enumerate(request.steps)
    }

    steps_dicts = [s.model_dump(exclude={"step_id"}) for s in request.steps]
    raw_scenes = await scene_service.generate_scenes(
        request.file_uri, request.mime_type, steps_dicts, language
    )

    return SceneResponse(
        scenes=scene_service.assemble(raw_scenes, step_number_to_id)
    )
