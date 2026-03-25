import random
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from models.schemas import (
    GenerateRequest, GenerateResponse,
    OptionsRequest, OptionsResponse,
    CheckRequest, CheckResponse,
)
from services.gemini import gemini_service
from services.cache import cache_service
from core.config import get_settings
from routers.emotions import get_random_emotions

router = APIRouter(prefix="/quiz", tags=["quiz"])
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=GenerateResponse)
async def generate_description(req: GenerateRequest):
    settings = get_settings()

    # 1. 캐시 확인
    cached = await cache_service.get_description(
        req.emotion_name, req.difficulty, req.seed
    )
    if cached:
        logger.info(f"[CACHE HIT] {req.emotion_name} / {req.difficulty}")
        return GenerateResponse(description=cached, cached=True)

    # 2. Gemini 호출
    try:
        description = await gemini_service.generate_description(
            req.emotion_name, req.emotion_en, req.difficulty
        )
        # 실제 응답 로그 — 잘리는지 확인용
        logger.info(f"[GEMINI] {req.emotion_name} → '{description}'")
    except Exception as e:
        logger.error(f"[GEMINI ERROR] {req.emotion_name}: {e}")
        raise HTTPException(status_code=502, detail=f"Gemini API 오류: {e}")

    # 3. 캐시 저장
    await cache_service.set_description(
        req.emotion_name, req.difficulty, description,
        ttl=settings.cache_ttl, seed=req.seed,
    )

    return GenerateResponse(description=description, cached=False)


@router.post("/generate/stream")
async def stream_description(req: GenerateRequest):
    settings = get_settings()

    cached = await cache_service.get_description(
        req.emotion_name, req.difficulty, req.seed
    )
    if cached:
        async def cached_stream():
            yield f"data: {cached}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    full_text = []

    async def event_stream():
        async for chunk in gemini_service.stream_description(
            req.emotion_name, req.emotion_en, req.difficulty
        ):
            full_text.append(chunk)
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

        complete = "".join(full_text)
        logger.info(f"[GEMINI STREAM] {req.emotion_name} → '{complete}'")
        await cache_service.set_description(
            req.emotion_name, req.difficulty, complete,
            ttl=settings.cache_ttl, seed=req.seed,
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/options", response_model=OptionsResponse)
async def get_options(req: OptionsRequest):
    wrong = get_random_emotions(
        exclude_name=req.correct_name,
        count=req.count - 1,
    )
    from routers.emotions import _ALL_EMOTIONS
    correct_data = next(
        (e for e in _ALL_EMOTIONS if e["name"] == req.correct_name), None
    )
    if not correct_data:
        raise HTTPException(status_code=404, detail="감정을 찾을 수 없습니다.")

    options = [correct_data] + wrong
    random.shuffle(options)

    return OptionsResponse(
        options=[{"name": o["name"], "emoji": o["emoji"]} for o in options]
    )


@router.post("/check", response_model=CheckResponse)
async def check_answer(req: CheckRequest):
    try:
        is_correct = await gemini_service.check_answer(
            req.user_answer, req.correct_answer
        )
    except Exception as e:
        is_correct = req.user_answer.strip() == req.correct_answer.strip()

    return CheckResponse(
        is_correct=is_correct,
        score_delta=10 if is_correct else 0,
    )