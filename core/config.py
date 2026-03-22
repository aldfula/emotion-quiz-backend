from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    gemini_api_key: str
    redis_url: str = "redis://localhost:6379"
    allowed_origins: str = "http://localhost:3000,http://localhost:8081"
    port: int = 8000

    # Gemini 모델
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_tokens: int = 1000

    # 캐시 TTL (초)
    cache_ttl: int = 86400  # 24시간

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()