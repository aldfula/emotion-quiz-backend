import random
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


@router.post("/generate", response_model=GenerateResponse)
async def generate_description(req: GenerateRequest):
    """
    감정 설명 생성.
    캐시 히트 시 Claude 호출 없이 즉시 반환.
    """
    settings = get_settings()

    # 1. 캐시 확인
    cached = await cache_service.get_description(
        req.emotion_name, req.difficulty, req.seed
    )
    if cached:
        return GenerateResponse(description=cached, cached=True)

    # 2. gemini 호출
    try:
        description = await gemini_service.generate_description(
            req.emotion_name, req.emotion_en, req.difficulty
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"gemini API 오류: {e}")

    # 3. 캐시 저장
    await cache_service.set_description(
        req.emotion_name, req.difficulty, description,
        ttl=settings.cache_ttl, seed=req.seed,
    )

    return GenerateResponse(description=description, cached=False)


@router.post("/generate/stream")
async def stream_description(req: GenerateRequest):
    """
    감정 설명을 SSE(Server-Sent Events)로 스트리밍.
    캐시 히트 시에도 일반 텍스트로 즉시 반환.
    """
    settings = get_settings()

    # 캐시 히트면 스트림 없이 바로 반환
    cached = await cache_service.get_description(
        req.emotion_name, req.difficulty, req.seed
    )
    if cached:
        async def cached_stream():
            yield f"data: {cached}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    # 스트리밍 생성
    full_text = []

    async def event_stream():
        async for chunk in gemini_service.stream_description(
            req.emotion_name, req.emotion_en, req.difficulty
        ):
            full_text.append(chunk)
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

        # 완성된 텍스트 캐시 저장 (백그라운드에서 처리하려면 BackgroundTasks 사용 가능)
        complete = "".join(full_text)
        await cache_service.set_description(
            req.emotion_name, req.difficulty, complete,
            ttl=settings.cache_ttl, seed=req.seed,
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/options", response_model=OptionsResponse)
async def get_options(req: OptionsRequest):
    """
    MCQ 보기 생성.
    정답 1개 + 랜덤 오답 (count-1)개를 섞어서 반환.
    """
    wrong = get_random_emotions(
        exclude_name=req.correct_name,
        count=req.count - 1,
    )
    # 정답 포함 후 셔플
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
    """
    주관식 답변 채점.
    gemini가 의미적 유사도를 판단.
    """
    try:
        is_correct = await gemini_service.check_answer(
            req.user_answer, req.correct_answer
        )
    except Exception as e:
        # Claude 호출 실패 시 단순 문자열 비교로 폴백
        is_correct = req.user_answer.strip() == req.correct_answer.strip()

    return CheckResponse(
        is_correct=is_correct,
        score_delta=10 if is_correct else 0,
    )
