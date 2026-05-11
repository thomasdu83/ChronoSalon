from __future__ import annotations

import json
import logging
from typing import Any

from chronosalon.catalog import moderator_character
from chronosalon.models import RoomDraft
from chronosalon.services.llm_client import OpenAICompatibleModelClient

logger = logging.getLogger(__name__)


class TopicIntelligence:
    """Use the room_builder LLM role to propose room drafts, then normalize them."""

    def __init__(self, model_client: OpenAICompatibleModelClient) -> None:
        self.model_client = model_client

    def build(self, topic: str, room_type: str | None = None) -> RoomDraft | None:
        if not self.model_client.is_available("room_builder"):
            return None

        content = self.model_client.complete(
            "room_builder",
            self._system_prompt(),
            self._user_prompt(topic, room_type),
            timeout=30.0,
        )
        if not content:
            return None

        payload = self._parse_payload(content)
        if not payload:
            return None
        return self._draft_from_payload(topic, payload, room_type)

    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是 ChronoSalon 的历史主题识别与建房助手。"
            "你的任务是把学生输入的主题转换成结构化聊天室草稿。"
            "必须优先保证史实边界和可用性，不能为了显得聪明而编造不确定人物。"
            "只输出 JSON 对象，不要 Markdown，不要解释。"
            "如果无法可靠确定主题所属时代、关键人物和讨论边界，就输出 status=needs_choice。"
            "如果输出 ready，必须满足："
            "1) 包含群主；2) 至少 3 个非群主历史人物或群体角色；"
            "3) historical_scene 必须包含 time_range 与 scene_allowed_eras；"
            "4) 至少 3 个 recommended_questions，且至少一个以 @人物 开头。"
        )

    @staticmethod
    def _user_prompt(topic: str, room_type: str | None) -> str:
        return json.dumps(
            {
                "topic": topic,
                "preferred_room_type": room_type or "auto",
                "requirements": {
                    "status": ["ready", "needs_choice"],
                    "room_type": ["historical_scene", "cross_time", None],
                    "characters_min_non_moderator": 3,
                    "recommended_questions_min": 3,
                },
                "output_schema": {
                    "status": "ready|needs_choice",
                    "room_title": "string",
                    "room_type": "historical_scene|cross_time|null",
                    "topic_boundary": "string",
                    "time_range": "string",
                    "learning_goals": ["string"],
                    "characters": [
                        {
                            "name": "string",
                            "type": "moderator|core_character|group_character",
                            "era": "string",
                            "identity": "string",
                            "role": "string",
                        }
                    ],
                    "recommended_questions": ["string"],
                    "source_pack_query": ["string"],
                    "options": ["string"],
                    "scene_allowed_eras": ["string"],
                    "scene_forbidden_names": ["string"],
                    "comparison_dimensions": ["string"],
                    "simulation_rules": ["string"],
                },
            },
            ensure_ascii=False,
        )

    def _draft_from_payload(
        self, topic: str, payload: dict[str, Any], requested_room_type: str | None
    ) -> RoomDraft | None:
        status = str(payload.get("status", "")).strip()
        if status not in {"ready", "needs_choice"}:
            logger.info(
                "Topic intelligence returned invalid status for topic=%s", topic
            )
            return None

        room_type = self._normalize_room_type(payload.get("room_type"))
        if status == "needs_choice":
            room_type = None
        if status == "ready" and not room_type:
            logger.info(
                "Topic intelligence returned ready without room_type for topic=%s",
                topic,
            )
            return None
        if requested_room_type and room_type and room_type != requested_room_type:
            logger.info(
                "Topic intelligence returned mismatched room_type for topic=%s requested=%s actual=%s",
                topic,
                requested_room_type,
                room_type,
            )
            return None

        room_title = self._clean_text(payload.get("room_title")) or topic
        topic_boundary = self._clean_text(payload.get("topic_boundary"))
        time_range = self._clean_text(payload.get("time_range"))
        learning_goals = self._clean_list(payload.get("learning_goals"))
        recommended_questions = self._clean_list(payload.get("recommended_questions"))
        source_pack_query = self._clean_list(payload.get("source_pack_query")) or [
            topic,
            f"{topic} 背景",
            f"{topic} 影响",
        ]
        options = self._clean_list(payload.get("options"))
        scene_allowed_eras = self._clean_list(payload.get("scene_allowed_eras"))
        scene_forbidden_names = self._clean_list(payload.get("scene_forbidden_names"))
        comparison_dimensions = self._clean_list(payload.get("comparison_dimensions"))
        simulation_rules = self._clean_list(payload.get("simulation_rules"))

        characters = self._normalize_characters(payload.get("characters"))
        if status == "ready" and not any(
            item.get("type") == "moderator" for item in characters
        ):
            characters.insert(0, moderator_character())
        if status == "needs_choice":
            time_range = ""
            characters = []
            recommended_questions = []
            scene_allowed_eras = []
            scene_forbidden_names = []
            comparison_dimensions = []
            simulation_rules = []
            options = options or self._default_choice_options(topic)

        if room_type == "cross_time":
            comparison_dimensions = comparison_dimensions or [
                "时代背景",
                "权力结构",
                "核心矛盾",
                "支持力量",
                "反对力量",
                "历史影响",
            ]
            simulation_rules = simulation_rules or [
                "这是跨时空假想讨论，不是真实历史现场。",
                "人物可以参考公共背景资料，但发言仍保持本时代立场。",
            ]

        return RoomDraft(
            status=status,
            room_title=room_title,
            room_type=room_type,
            topic_boundary=topic_boundary,
            time_range=time_range,
            learning_goals=learning_goals,
            characters=characters,
            recommended_questions=recommended_questions,
            source_pack_query=source_pack_query,
            options=options,
            comparison_dimensions=comparison_dimensions,
            simulation_rules=simulation_rules,
            scene_allowed_eras=scene_allowed_eras,
            scene_forbidden_names=scene_forbidden_names,
        )

    @staticmethod
    def _parse_payload(content: str) -> dict[str, Any] | None:
        normalized = content.strip()
        if normalized.startswith("```"):
            lines = [
                line
                for line in normalized.splitlines()
                if not line.strip().startswith("```")
            ]
            normalized = "\n".join(lines).strip()
        start = normalized.find("{")
        end = normalized.rfind("}")
        if start == -1 or end == -1 or end < start:
            return None
        try:
            payload = json.loads(normalized[start : end + 1])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _normalize_room_type(value: Any) -> str | None:
        normalized = str(value).strip()
        return normalized if normalized in {"historical_scene", "cross_time"} else None

    @staticmethod
    def _clean_text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _clean_list(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = cls._clean_text(item)
            if not text or text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        return cleaned

    @classmethod
    def _normalize_characters(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        characters: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            name = cls._clean_text(item.get("name"))
            if not name or name in seen_names:
                continue
            seen_names.add(name)

            character_type = cls._normalize_character_type(item.get("type"), name)
            payload: dict[str, Any] = {
                "id": cls._clean_text(item.get("id")) or f"llm_character_{index}",
                "name": name,
                "type": character_type,
                "era": cls._clean_text(item.get("era")) or "待确认",
                "identity": cls._clean_text(item.get("identity")) or name,
                "role": cls._clean_text(item.get("role"))
                or cls._clean_text(item.get("identity"))
                or name,
            }
            if character_type == "group_character" or name.endswith("代表"):
                payload["must_label"] = "群体立场模拟，不代表某个具体历史人物原话。"
            characters.append(payload)
        return characters

    @staticmethod
    def _normalize_character_type(value: Any, name: str) -> str:
        normalized = str(value).strip()
        if normalized in {"moderator", "core_character", "group_character"}:
            return normalized
        if name == "群主":
            return "moderator"
        if name.endswith("代表"):
            return "group_character"
        return "core_character"

    @staticmethod
    def _default_choice_options(topic: str) -> list[str]:
        return [
            f"{topic} 背景",
            f"{topic} 关键人物",
            f"{topic} 为什么重要",
            f"{topic} 最精彩的转折",
        ]
