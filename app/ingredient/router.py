from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.container import Container
from app.ingredient.schema import IngredientsRequest, IngredientsResponse
from app.ingredient.service import IngredientService

router = APIRouter()

@router.post("/v1/ingredients", response_model=IngredientsResponse)
@inject
async def extract_ingredients(
    request: IngredientsRequest,
    ingredient_service: IngredientService = Depends(Provide[Container.ingredient_service])
):
    ingredients = await ingredient_service.extract(request.video_id, request.captions_data.captions, request.captions_data.lang_code)
    return IngredientsResponse(
        ingredients=ingredients
    )