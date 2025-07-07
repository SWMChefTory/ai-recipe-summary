import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator

from app.api.recipes import router as recipe_router
from app.container import container

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    # Startup
    logger.info("🚀 Recipe Summarizer API 시작 중...")
    # 의존성 주입 컨테이너 설정
    container.wire(modules=[__name__])
    yield
    # Shutdown
    logger.info("🔄 Recipe Summarizer API 종료 중...")


# FastAPI 앱 생성 (lifespan 이벤트 핸들러 포함)
app = FastAPI(
    title="Recipe Summarizer", 
    version="1.0.0",
    lifespan=lifespan
)

# 라우터 등록
app.include_router(recipe_router)

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {"message": "Recipe Summarizer API - 객체지향 구조로 리팩토링 완료"}


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy", "version": "1.0.0"}
