from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from chronosalon.app import ChronoSalonApp
from chronosalon.services.llm_client import OpenAICompatibleModelClient
from chronosalon.services.topic_intelligence import TopicIntelligence


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "src" / "config" / "model_config.yaml"
ENV_PATH = ROOT / "src" / ".env"
FRONTEND_DIR = ROOT / "frontend"


class BuildRoomRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    student_level: str = "middle_or_high_school"
    room_type: str = "auto"


class ChatRequest(BaseModel):
    room: dict[str, Any]
    message: str = Field(..., min_length=1)
    recent_messages: list[dict[str, Any]] = Field(default_factory=list)
    use_llm: bool = True


class ReviewRequest(BaseModel):
    room: dict[str, Any]
    messages: list[dict[str, Any]] = Field(default_factory=list)


def build_default_topic_intelligence() -> TopicIntelligence | None:
    try:
        return TopicIntelligence(OpenAICompatibleModelClient(CONFIG_PATH, ENV_PATH))
    except Exception:
        return None


def create_api_app(topic_intelligence: TopicIntelligence | None = None) -> FastAPI:
    api = FastAPI(title="ChronoSalon API", version="0.1.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    shared_topic_intelligence = topic_intelligence or build_default_topic_intelligence()
    local_app = ChronoSalonApp(
        use_llm=False, topic_intelligence=shared_topic_intelligence
    )
    llm_app = ChronoSalonApp(
        use_llm=True,
        config_path=CONFIG_PATH,
        env_path=ENV_PATH,
        topic_intelligence=shared_topic_intelligence,
    )

    @api.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "chronosalon"}

    @api.post("/api/rooms/build")
    def build_room(request: BuildRoomRequest) -> dict[str, Any]:
        preferred_type = None if request.room_type == "auto" else request.room_type
        return local_app.build_room(request.topic, preferred_type)

    @api.post("/api/chat")
    def chat(request: ChatRequest) -> dict[str, Any]:
        app = llm_app if request.use_llm else local_app
        return app.chat(request.room, request.message, request.recent_messages)

    @api.post("/api/chat/plan")
    def chat_plan(request: ChatRequest) -> dict[str, Any]:
        return local_app.plan_chat(
            request.room, request.message, request.recent_messages
        )

    @api.post("/api/review")
    def review(request: ReviewRequest) -> dict[str, Any]:
        return llm_app.review(request.room, request.messages)

    if FRONTEND_DIR.exists():
        api.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

    return api


app = create_api_app()
