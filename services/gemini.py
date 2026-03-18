"""
Google Gemini API 래퍼.
- generate_description: 감정 설명 생성
- stream_description: 설명 스트리밍 (SSE용)
- check_answer: 주관식 답변 채점
"""
import logging
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from core.config import get_settings
from models.schemas import Difficulty
from typing import AsyncIterator
import asyncio

logger = logging.getLogger(__name__)

DIFFICULTY_PROMPTS: dict[str, str] = {
    Difficulty.easy: (
        "초등학생도 이해할 수 있도록 일상적인 예시를 들어 2~3문장으로 설명해. "
        "쉽고 친근한 표현만 사용해."
    ),
    Difficulty.normal: (
        "심리적 특징과 신체 반응을 포함해 2~3문장으로 설명해. "
        "일반 성인이 이해할 수 있는 수준으로 써."
    ),
    Difficulty.hard: (
        "철학적·심리학적 관점에서 유사 감정과의 미묘한 차이를 포함해 2~3문장으로 설명해. "
        "전문 용어를 적절히 사용해도 좋아."
    ),
}


def _build_prompt(emotion_name: str, emotion_en: str, difficulty: Difficulty) -> str:
    diff_instruction = DIFFICULTY_PROMPTS[difficulty]
    return (
        f"감정: \"{emotion_name}\" (영어: {emotion_en})\n\n"
        f"{diff_instruction}\n\n"
        "규칙:\n"
        "- 감정 이름(한국어/영어) 절대 포함 금지\n"
        "- 설명 텍스트만 출력, 다른 말 없이\n"
        "- 반드시 완전한 문장으로 마침표(.)로 끝낼 것\n"
        "- 문장을 절대 중간에 자르지 말 것"
    )


class GeminiService:
    def __init__(self):
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        self._model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            generation_config=GenerationConfig(
                max_output_tokens=settings.gemini_max_tokens,
                temperature=0.7,
            ),
        )

    async def generate_description(
        self,
        emotion_name: str,
        emotion_en: str,
        difficulty: Difficulty,
    ) -> str:
        """감정 설명을 한 번에 반환."""
        prompt = _build_prompt(emotion_name, emotion_en, difficulty)
        response = await asyncio.to_thread(
            self._model.generate_content, prompt
        )
        return response.text.strip()

    async def stream_description(
        self,
        emotion_name: str,
        emotion_en: str,
        difficulty: Difficulty,
    ) -> AsyncIterator[str]:
        """설명을 청크 단위로 스트리밍 (SSE 엔드포인트용)."""
        prompt = _build_prompt(emotion_name, emotion_en, difficulty)
        response = await asyncio.to_thread(
            self._model.generate_content, prompt, stream=True  # type: ignore
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def check_answer(self, user_answer: str, correct_answer: str) -> bool:
        """주관식 답변이 정답과 의미상 같은지 판별."""
        prompt = (
            f"사용자 답변: \"{user_answer}\"\n"
            f"정답: \"{correct_answer}\"\n\n"
            "의미상 같거나 매우 유사한 한국어 감정 표현이면 YES, 아니면 NO만 출력."
        )
        response = await asyncio.to_thread(
            self._model.generate_content, prompt
        )
        result = response.text.strip().upper()
        return result.startswith("YES")


# 싱글톤
gemini_service = GeminiService()