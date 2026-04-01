import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.briefing.router import router as briefing_router
from app.container import container
from app.exception import BusinessException
from app.meta.router import router as meta_router
from app.scene.router import router as scene_router
from app.step.router import router as step_router
from app.verify.router import router as verify_router

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Uvicorn access log에서 /metrics 필터링
class UvicornMetricsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        request_line = getattr(record, "request_line", "")
        if isinstance(request_line, str) and " /metrics" in request_line:
            return False
        # 포매팅된 메시지 기준의 백업 체크 (환경에 따라 formatter가 다를 수 있음)
        try:
            message = record.getMessage()
        except Exception:
            message = ""
        return "/metrics" not in message

logging.getLogger("uvicorn.access").addFilter(UvicornMetricsFilter())

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    # Startup
    logger.info("🚀 Recipe Summarizer API 시작 중...")
    max_workers = 96
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=max_workers)
    loop.set_default_executor(executor)
    logger.info(f"🔧 asyncio default thread pool 설정 완료 | max_workers={max_workers}")
    # 의존성 주입 컨테이너 설정
    container.wire(modules=[__name__])
    yield
    # Shutdown
    executor.shutdown(wait=False, cancel_futures=False)
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
app.include_router(meta_router)
app.include_router(step_router)
app.include_router(scene_router)
app.include_router(briefing_router)
app.include_router(verify_router)
