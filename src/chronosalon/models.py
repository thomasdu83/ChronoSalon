from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

RoomType = Literal["historical_scene", "cross_time"]
CharacterType = Literal["core_character", "group_character", "moderator", "temporary_character"]
BuildStatus = Literal["ready", "needs_choice"]


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    era: str
    identity: str
    character_type: CharacterType = "core_character"
    role: str = ""
    core_positions: list[str] = field(default_factory=list)
    knowledge_boundary: dict[str, str] = field(default_factory=dict)
    language_style: dict[str, Any] = field(default_factory=dict)
    chat_behavior: dict[str, Any] = field(default_factory=dict)
    must_do: list[str] = field(default_factory=list)
    must_not: list[str] = field(default_factory=list)
    source_scope: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "era": self.era,
            "identity": self.identity,
            "type": self.character_type,
            "role": self.role,
            "core_positions": list(self.core_positions),
            "knowledge_boundary": dict(self.knowledge_boundary),
            "language_style": dict(self.language_style),
            "chat_behavior": dict(self.chat_behavior),
            "must_do": list(self.must_do),
            "must_not": list(self.must_not),
            "source_scope": list(self.source_scope),
        }


@dataclass(frozen=True)
class RoomDraft:
    status: BuildStatus
    room_title: str
    room_type: RoomType | None
    topic_boundary: str
    time_range: str = ""
    learning_goals: list[str] = field(default_factory=list)
    characters: list[dict[str, Any]] = field(default_factory=list)
    recommended_questions: list[str] = field(default_factory=list)
    source_pack_query: list[str] = field(default_factory=list)
    options: list[str] = field(default_factory=list)
    comparison_dimensions: list[str] = field(default_factory=list)
    simulation_rules: list[str] = field(default_factory=list)
    scene_allowed_eras: list[str] = field(default_factory=list)
    scene_forbidden_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "room_title": self.room_title,
            "room_type": self.room_type,
            "topic_boundary": self.topic_boundary,
            "time_range": self.time_range,
            "learning_goals": list(self.learning_goals),
            "characters": list(self.characters),
            "recommended_questions": list(self.recommended_questions),
            "source_pack_query": list(self.source_pack_query),
            "options": list(self.options),
            "comparison_dimensions": list(self.comparison_dimensions),
            "simulation_rules": list(self.simulation_rules),
            "scene_allowed_eras": list(self.scene_allowed_eras),
            "scene_forbidden_names": list(self.scene_forbidden_names),
        }


@dataclass(frozen=True)
class Message:
    sender_type: Literal["student", "character", "moderator", "system"]
    sender_name: str
    content: str
    labels: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sender_type": self.sender_type,
            "sender_name": self.sender_name,
            "content": self.content,
            "labels": list(self.labels),
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class SpeakerStep:
    speaker: str
    task: str

    def to_dict(self) -> dict[str, str]:
        return {"speaker": self.speaker, "task": self.task}


@dataclass(frozen=True)
class OrchestrationPlan:
    intent: str
    target_character: str | None
    needs_retrieval: bool
    retrieval_queries: list[str]
    speaker_sequence: list[SpeakerStep]
    max_auto_messages: int = 4

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "target_character": self.target_character,
            "needs_retrieval": self.needs_retrieval,
            "retrieval_queries": list(self.retrieval_queries),
            "speaker_sequence": [step.to_dict() for step in self.speaker_sequence],
            "max_auto_messages": self.max_auto_messages,
        }
