from pydantic import BaseModel
from enum import Enum


class Difficulty(str, Enum):
    easy = "easy"
    normal = "normal"
    hard = "hard"


class QuizMode(str, Enum):
    mcq = "mcq"
    subjective = "subjective"
    flash = "flash"


# ── /quiz/generate ──────────────────────────────────────────
class GenerateRequest(BaseModel):
    emotion_name: str       # 예: "기쁨"
    emotion_en: str         # 예: "joy"
    difficulty: Difficulty
    seed: int | None = None  # 같은 감정도 다른 설명을 원할 때


class GenerateResponse(BaseModel):
    description: str
    cached: bool


# ── /quiz/options ────────────────────────────────────────────
class OptionsRequest(BaseModel):
    correct_name: str
    count: int = 4          # 보기 개수


class OptionsResponse(BaseModel):
    options: list[dict]     # [{name, emoji}, ...]


# ── /quiz/check ──────────────────────────────────────────────
class CheckRequest(BaseModel):
    user_answer: str
    correct_answer: str


class CheckResponse(BaseModel):
    is_correct: bool
    score_delta: int        # 맞으면 10, 틀리면 0


# ── /emotions ────────────────────────────────────────────────
class Emotion(BaseModel):
    name: str
    emoji: str
    en: str


class EmotionsResponse(BaseModel):
    emotions: list[Emotion]
    total: int
