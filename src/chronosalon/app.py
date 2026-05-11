from __future__ import annotations

from typing import Any
from pathlib import Path

from chronosalon.services.orchestrator import Orchestrator
from chronosalon.services.llm_client import OpenAICompatibleModelClient
from chronosalon.services.responder import run_hybrid_speaking_plan, run_speaking_plan
from chronosalon.services.review_generator import ReviewGenerator
from chronosalon.services.room_builder import RoomBuilder
from chronosalon.services.topic_intelligence import TopicIntelligence
from chronosalon.services.character_manager import (
    extract_mentions,
    prepare_mentioned_character,
)
from chronosalon.catalog import MODERATOR_NAME, is_moderator_name
from chronosalon.models import OrchestrationPlan, SpeakerStep, Message


class ChronoSalonApp:
    def __init__(
        self,
        use_llm: bool = False,
        config_path: str | Path | None = None,
        env_path: str | Path | None = None,
        topic_intelligence: TopicIntelligence | None = None,
    ) -> None:
        self.orchestrator = Orchestrator()
        self.use_llm = use_llm
        self.model_client = (
            OpenAICompatibleModelClient(config_path, env_path)
            if use_llm and config_path
            else None
        )
        self.review_generator = ReviewGenerator(self.model_client)
        self.topic_intelligence = topic_intelligence or (
            TopicIntelligence(self.model_client) if self.model_client else None
        )
        self.room_builder = RoomBuilder(topic_intelligence=self.topic_intelligence)

    def build_room(self, topic: str, room_type: str | None = None) -> dict[str, Any]:
        return self.room_builder.build(topic, room_type=room_type).to_dict()

    def plan_chat(
        self,
        room: dict[str, Any],
        user_message: str,
        recent_messages: list[dict] | None = None,
    ) -> dict[str, Any]:
        mention_state = prepare_mentioned_character(room, user_message)
        room = mention_state["room"]
        if mention_state["blocked_reason"]:
            plan = OrchestrationPlan(
                intent="blocked_cross_time_mention",
                target_character=MODERATOR_NAME,
                needs_retrieval=False,
                retrieval_queries=[],
                speaker_sequence=[
                    SpeakerStep(MODERATOR_NAME, mention_state["blocked_reason"])
                ],
                max_auto_messages=1,
            )
            return {
                "room": room,
                "added_character": None,
                "blocked_reason": mention_state["blocked_reason"],
                "plan": plan.to_dict(),
            }

        plan = self.orchestrator.plan(room, user_message, recent_messages)
        return {
            "room": room,
            "added_character": mention_state["added_character"],
            "blocked_reason": None,
            "plan": plan.to_dict(),
        }

    def chat(
        self,
        room: dict[str, Any],
        user_message: str,
        recent_messages: list[dict] | None = None,
    ) -> dict[str, Any]:
        planned = self.plan_chat(room, user_message, recent_messages)
        room = planned["room"]
        if planned["blocked_reason"]:
            message = Message(
                sender_type="moderator",
                sender_name=MODERATOR_NAME,
                content=planned["blocked_reason"],
                labels=["时空边界提醒", "群聊主持"],
            ).to_dict()
            return {
                "room": room,
                "added_character": None,
                "blocked_reason": planned["blocked_reason"],
                "plan": planned["plan"],
                "messages": [message],
            }

        plan = OrchestrationPlan(
            intent=planned["plan"]["intent"],
            target_character=planned["plan"]["target_character"],
            needs_retrieval=planned["plan"]["needs_retrieval"],
            retrieval_queries=planned["plan"]["retrieval_queries"],
            speaker_sequence=[
                SpeakerStep(item["speaker"], item["task"])
                for item in planned["plan"]["speaker_sequence"]
            ],
            max_auto_messages=planned["plan"]["max_auto_messages"],
        )
        if self.use_llm:
            messages = run_hybrid_speaking_plan(
                room, plan, user_message, self.model_client, recent_messages
            )
        else:
            messages = run_speaking_plan(room, plan, user_message, recent_messages)

        handoff = self._append_moderator_mentioned_reply(
            room, plan, user_message, recent_messages or [], messages
        )
        room = handoff["room"]
        messages = handoff["messages"]
        added_character = planned["added_character"] or handoff["added_character"]
        return {
            "room": room,
            "added_character": added_character,
            "blocked_reason": None,
            "plan": planned["plan"],
            "messages": messages,
        }

    def review(
        self, room: dict[str, Any], messages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return self.review_generator.generate(room, messages)

    def _append_moderator_mentioned_reply(
        self,
        room: dict[str, Any],
        plan: OrchestrationPlan,
        user_message: str,
        recent_messages: list[dict[str, Any]],
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        empty_result = {"room": room, "messages": messages, "added_character": None}
        if plan.intent != "general_question" or not messages or len(plan.speaker_sequence) > 1:
            return empty_result
        moderator_message = messages[-1]
        if not is_moderator_name(moderator_message.get("sender_name")):
            return empty_result

        mention_state = prepare_mentioned_character(
            room, moderator_message.get("content", "")
        )
        if mention_state["blocked_reason"]:
            return empty_result
        room = mention_state["room"]
        mentioned = self._first_room_character_mentioned_by_moderator(
            room, moderator_message.get("content", "")
        )
        if not mentioned:
            return empty_result

        followup_plan = OrchestrationPlan(
            intent="moderator_handoff",
            target_character=mentioned,
            needs_retrieval=True,
            retrieval_queries=[room.get("room_title", ""), mentioned, user_message],
            speaker_sequence=[
                SpeakerStep(
                    mentioned,
                    "接住群主刚才点名和学生原话，结合最近上下文发言；不要重新开场，不要无视前文。",
                )
            ],
            max_auto_messages=1,
        )
        followup_context = [
            *recent_messages,
            {"sender_name": "我", "sender_type": "student", "content": user_message},
            moderator_message,
        ]
        if self.use_llm:
            followups = run_hybrid_speaking_plan(
                room, followup_plan, user_message, self.model_client, followup_context
            )
        else:
            followups = run_speaking_plan(
                room, followup_plan, user_message, followup_context
            )
        return {
            "room": room,
            "messages": [*messages, *followups],
            "added_character": mention_state["added_character"],
        }

    @staticmethod
    def _first_room_character_mentioned_by_moderator(
        room: dict[str, Any], content: str
    ) -> str | None:
        names = [
            item.get("name")
            for item in room.get("characters", [])
            if item.get("name") and not is_moderator_name(item.get("name"))
        ]
        for mention in extract_mentions(content):
            for name in names:
                if mention == name or mention.startswith(name):
                    return name
        return None
