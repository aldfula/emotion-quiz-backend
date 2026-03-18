"""
Redis 캐시 서비스.
Redis 연결 실패 시 인메모리 딕셔너리로 자동 폴백 — 개발 환경에서 Redis 없이도 동작.
"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class InMemoryCache:
    """Redis 없을 때 사용하는 간단한 인메모리 캐시."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value  # TTL 미지원 (개발용)

    async def ping(self) -> bool:
        return True


class CacheService:
    def __init__(self):
        self._client = None
        self._using_redis = False

    async def init(self, redis_url: str) -> None:
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(redis_url, decode_responses=True)
            await client.ping()
            self._client = client
            self._using_redis = True
            logger.info("Redis 연결 성공")
        except Exception as e:
            logger.warning(f"Redis 연결 실패 ({e}) → 인메모리 캐시로 폴백")
            self._client = InMemoryCache()

    def _make_key(self, emotion_name: str, difficulty: str, seed: int | None) -> str:
        seed_part = f":{seed}" if seed is not None else ""
        return f"desc:{emotion_name}:{difficulty}{seed_part}"

    async def get_description(
        self, emotion_name: str, difficulty: str, seed: int | None = None
    ) -> str | None:
        key = self._make_key(emotion_name, difficulty, seed)
        raw = await self._client.get(key)
        return raw if raw else None

    async def set_description(
        self,
        emotion_name: str,
        difficulty: str,
        description: str,
        ttl: int = 86400,
        seed: int | None = None,
    ) -> None:
        key = self._make_key(emotion_name, difficulty, seed)
        await self._client.set(key, description, ex=ttl)

    @property
    def using_redis(self) -> bool:
        return self._using_redis


# 싱글톤
cache_service = CacheService()
