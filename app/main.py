import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.briefing.router import router as briefing_router
from app.caption.router import router as caption_router
from app.container import container
from app.exception import BusinessException
from app.meta.router import router as meta_router
from app.step.router import router as step_router

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

Instrumentator().instrument(app).expose(app)

@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    logger.info("business_exception", extra={"path": str(request.url), "error_code": exc.error_code})
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

# 라우터 등록
app.include_router(caption_router)
app.include_router(meta_router)
app.include_router(step_router)
app.include_router(briefing_router)