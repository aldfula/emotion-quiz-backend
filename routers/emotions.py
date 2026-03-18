import json
import random
from pathlib import Path
from fastapi import APIRouter, Query
from models.schemas import Emotion, EmotionsResponse

router = APIRouter(prefix="/emotions", tags=["emotions"])

# 앱 시작 시 한 번만 로드
_DATA_PATH = Path(__file__).parent.parent / "data" / "emotions.json"
_ALL_EMOTIONS: list[dict] = json.loads(_DATA_PATH.read_text(encoding="utf-8"))


@router.get("", response_model=EmotionsResponse)
async def get_emotions(
    shuffle: bool = Query(False, description="랜덤 순서로 반환"),
    limit: int = Query(100, ge=1, le=100, description="반환할 감정 수"),
):
    """감정 목록 반환. 퀴즈 시작 시 한 번 호출해 클라이언트가 캐시."""
    emotions = _ALL_EMOTIONS.copy()
    if shuffle:
        random.shuffle(emotions)
    emotions = emotions[:limit]
    return EmotionsResponse(
        emotions=[Emotion(**e) for e in emotions],
        total=len(_ALL_EMOTIONS),
    )


def get_random_emotions(exclude_name: str, count: int = 3) -> list[dict]:
    """MCQ 오답 보기 생성용 헬퍼."""
    pool = [e for e in _ALL_EMOTIONS if e["name"] != exclude_name]
    return random.sample(pool, min(count, len(pool)))
