import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from services.cache import cache_service
from routers import emotions, quiz

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 시작 ──
    settings = get_settings()
    await cache_service.init(settings.redis_url)
    logger.info(f"캐시 백엔드: {'Redis' if cache_service.using_redis else '인메모리'}")
    yield
    # ── 종료 ──
    logger.info("서버 종료")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="감정 탐구 퀴즈 API",
        description="100가지 감정 퀴즈 — Claude AI 설명 생성",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 라우터 등록
    app.include_router(emotions.router)
    app.include_router(quiz.router)

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "cache": "redis" if cache_service.using_redis else "memory",
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True)
