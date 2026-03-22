"""
Google Gemini API 래퍼.
"""
import logging
import asyncio
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from core.config import get_settings
from models.schemas import Difficulty
from typing import AsyncIterator

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15

DIFFICULTY_PROMPTS: dict[str, str] = {
    Difficulty.easy: (
        "초등학생도 이해할 수 있도록 일상적인 예시를 들어 1~2문장으로 설명해. "
        "쉽고 친근한 표현만 사용해."
    ),
    Difficulty.normal: (
        "심리적 특징과 신체 반응을 포함해 1~2문장으로 설명해. "
        "일반 성인이 이해할 수 있는 수준으로 써."
    ),
    Difficulty.hard: (
        "철학적·심리학적 관점에서 유사 감정과의 미묘한 차이를 포함해 1~2문장으로 설명해. "
        "전문 용어를 적절히 사용해도 좋아."
    ),
}


def _build_prompt(emotion_name: str, emotion_en: str, difficulty: Difficulty) -> str:
    diff_instruction = DIFFICULTY_PROMPTS[difficulty]
    # 규칙을 System Instruction으로 넘겼으므로, 여기서는 핵심 정보만 전달합니다.
    return (
        f"감정: \"{emotion_name}\" (영어: {emotion_en})\n\n"
        f"조건: {diff_instruction}"
    )
    diff_instruction = DIFFICULTY_PROMPTS[difficulty]
    return (
        f"감정: \"{emotion_name}\" (영어: {emotion_en})\n\n"
        f"{diff_instruction}\n\n"
        "규칙:\n"
        "- 감정 이름(한국어/영어) 절대 포함 금지\n"
        "- 설명 텍스트만 출력, 다른 말 없이\n"
        "- 반드시 마침표(.)로 끝나는 완전한 문장으로 작성\n"
        "- 주어진 토큰 내에서 반드시 문장을 완결지을 것\n"
        "- 문장이 잘릴 것 같으면 더 짧게 써서라도 완전히 끝낼 것"
    )


class GeminiService:
    def __init__(self):
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        
        # 시스템 지시어 추가
        sys_instruct = (
            "너는 감정을 1~2문장으로 짧고 명확하게 설명하는 사전이야. "
            "감정 이름(한국어/영어)은 절대 포함하지 말고 설명 텍스트만 출력해. "
            "반드시 마침표(.)로 끝나는 완전한 문장으로 작성해."
        )
        
        self._model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=sys_instruct,
            generation_config=GenerationConfig(
                max_output_tokens=settings.gemini_max_tokens,
                temperature=0.4,  # 0.7에서 0.4로 하향
                # stop_sequences=["...", "…"],  # 말줄임표 차단 로직 제거
            ),
        )

    async def generate_description(
        self,
        emotion_name: str,
        emotion_en: str,
        difficulty: Difficulty,
    ) -> str:
        prompt = _build_prompt(emotion_name, emotion_en, difficulty)
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(self._model.generate_content, prompt),
                timeout=TIMEOUT_SECONDS,
            )
            return response.text.strip()
        except asyncio.TimeoutError:
            raise TimeoutError(f"Gemini API 응답 초과 ({TIMEOUT_SECONDS}초)")

    async def stream_description(
        self,
        emotion_name: str,
        emotion_en: str,
        difficulty: Difficulty,
    ) -> AsyncIterator[str]:
        prompt = _build_prompt(emotion_name, emotion_en, difficulty)
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(self._model.generate_content, prompt, stream=True),  # type: ignore
                timeout=TIMEOUT_SECONDS,
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except asyncio.TimeoutError:
            raise TimeoutError(f"Gemini API 응답 초과 ({TIMEOUT_SECONDS}초)")

    async def check_answer(self, user_answer: str, correct_answer: str) -> bool:
        prompt = (
            f"사용자 답변: \"{user_answer}\"\n"
            f"정답: \"{correct_answer}\"\n\n"
            "의미상 같거나 매우 유사한 한국어 감정 표현이면 YES, 아니면 NO만 출력."
        )
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(self._model.generate_content, prompt),
                timeout=10,
            )
            return response.text.strip().upper().startswith("YES")
        except asyncio.TimeoutError:
            return False


# 싱글톤
gemini_service = GeminiService()