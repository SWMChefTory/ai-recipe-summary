import re

from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator

from app.api.recipes import router as recipe_router

app = FastAPI(title="Recipe Summarizer", version="1.0.0")
app.include_router(recipe_router)
