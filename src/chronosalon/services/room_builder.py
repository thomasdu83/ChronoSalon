from __future__ import annotations

from chronosalon.catalog import (
    BIG_TOPIC_OPTIONS,
    CROSS_TIME_REFORM_PROFILE,
    PERSON_TOPIC_OPTIONS,
    TOPIC_PROFILES,
    character_dict,
    group_character_dict,
    moderator_character,
)
from chronosalon.models import RoomDraft
from chronosalon.services.topic_intelligence import TopicIntelligence
from chronosalon.services.room_validator import RoomValidator
from chronosalon.services.smart_room_builder import SmartRoomBuilder


class RoomBuilder:
    """Build a structured room draft from a student's topic input."""

    cross_time_keywords = (
        "为什么",
        "比较",
        "不同",
        "相同",
        "总是",
        "是否",
        "哪个",
        "改革",
        "vs",
        "VS",
        "跨时空",
    )

    def __init__(self, topic_intelligence: TopicIntelligence | None = None) -> None:
        self.smart_room_builder = SmartRoomBuilder()
        self.room_validator = RoomValidator()
        self.topic_intelligence = topic_intelligence

    def build(
        self,
        raw_topic: str,
        student_level: str = "middle_or_high_school",
        room_type: str | None = None,
    ) -> RoomDraft:
        topic = self._normalize(raw_topic)
        requested_cross_time = room_type == "cross_time"
        requested_scene = room_type == "historical_scene"

        if not topic:
            return self.room_validator.validate(
                RoomDraft(
                    status="needs_choice",
                    room_title="选择一个历史主题",
                    room_type=None,
                    topic_boundary="请输入一个历史事件、人物或问题。",
                    options=["商鞅变法", "安史之乱", "为什么改革常常遇到阻力？"],
                )
            )

        if requested_cross_time:
            profile = self._cross_time_profile_for(topic)
            return self.room_validator.validate(self._from_cross_time_profile(profile))

        if topic in BIG_TOPIC_OPTIONS:
            return self.room_validator.validate(
                RoomDraft(
                    status="needs_choice",
                    room_title=topic,
                    room_type=None,
                    topic_boundary=f"“{topic}”范围较大，建议先拆成一个可讨论的具体主题。",
                    options=BIG_TOPIC_OPTIONS[topic],
                )
            )

        if topic in PERSON_TOPIC_OPTIONS and not requested_scene:
            return self.room_validator.validate(
                RoomDraft(
                    status="needs_choice",
                    room_title=topic,
                    room_type=None,
                    topic_boundary=f"“{topic}”可以从多个角度学习，建议先选择一个具体问题。",
                    options=PERSON_TOPIC_OPTIONS[topic],
                )
            )

        matched_topic = self._match_known_topic(topic)
        if matched_topic:
            return self.room_validator.validate(self._from_topic_profile(matched_topic))

        if self._looks_cross_time(topic):
            profile = self._cross_time_profile_for(topic)
            return self.room_validator.validate(self._from_cross_time_profile(profile))

        smart_room = self.smart_room_builder.build(topic)
        if smart_room:
            return self.room_validator.validate(smart_room)

        if self.topic_intelligence:
            llm_room = self.topic_intelligence.build(topic, room_type=room_type)
            if llm_room:
                return self.room_validator.validate(llm_room)

        return self.room_validator.validate(
            RoomDraft(
                status="needs_choice",
                room_title=topic,
                room_type=None,
                topic_boundary=f"系统暂时无法可靠识别“{topic}”对应的历史时空和核心人物，请先补充更具体的事件、时期或人物。",
                options=[
                    f"{topic} 背景",
                    f"{topic} 关键人物",
                    f"{topic} 发生在什么时期",
                    "商鞅变法",
                    "安史之乱",
                ],
            )
        )

    def _from_topic_profile(self, topic: str) -> RoomDraft:
        profile = TOPIC_PROFILES[topic]
        characters = [moderator_character()]
        characters.extend(
            character_dict(character_id) for character_id in profile["character_ids"]
        )
        characters.extend(
            group_character_dict(name) for name in profile["group_characters"]
        )
        return RoomDraft(
            status="ready",
            room_title=topic,
            room_type=profile["room_type"],
            topic_boundary=profile["topic_boundary"],
            time_range=profile["time_range"],
            learning_goals=list(profile["learning_goals"]),
            characters=characters,
            recommended_questions=list(profile["recommended_questions"]),
            source_pack_query=list(profile["source_pack_query"]),
            scene_allowed_eras=list(profile.get("scene_allowed_eras", [])),
            scene_forbidden_names=list(profile.get("scene_forbidden_names", [])),
        )

    def _from_cross_time_profile(self, profile: dict) -> RoomDraft:
        characters = [moderator_character()]
        characters.extend(
            character_dict(character_id) for character_id in profile["character_ids"]
        )
        characters.extend(
            group_character_dict(name) for name in profile["group_characters"]
        )
        return RoomDraft(
            status="ready",
            room_title=profile["room_title"],
            room_type=profile["room_type"],
            topic_boundary=profile["topic_boundary"],
            time_range=profile["time_range"],
            learning_goals=list(profile["learning_goals"]),
            characters=characters,
            recommended_questions=list(profile["recommended_questions"]),
            source_pack_query=list(profile["source_pack_query"]),
            comparison_dimensions=list(profile["comparison_dimensions"]),
            simulation_rules=list(profile["simulation_rules"]),
        )

    def _cross_time_profile_for(self, topic: str) -> dict:
        profile = dict(CROSS_TIME_REFORM_PROFILE)
        if "改革" not in topic:
            profile["room_title"] = topic
            profile["topic_boundary"] = f"围绕“{topic}”展开跨时空比较讨论。"
            profile["recommended_questions"] = [
                "@秦始皇 你怎么看这个问题？",
                "@汉武帝 你的做法有什么不同？",
                "请群主做一个比较表。",
            ]
            profile["character_ids"] = [
                "qin_shihuang",
                "han_wudi",
                "napoleon",
                "wang_anshi",
            ]
            profile["group_characters"] = ["保守派官僚代表"]
            profile["source_pack_query"] = [
                topic,
                f"{topic} 比较",
                f"{topic} 跨时空讨论",
            ]
            profile["comparison_dimensions"] = [
                "时代背景",
                "权力结构",
                "治理目标",
                "支持力量",
                "反对力量",
                "历史影响",
            ]
        return profile

    def _match_known_topic(self, topic: str) -> str | None:
        if topic in TOPIC_PROFILES:
            return topic
        for known in TOPIC_PROFILES:
            if known in topic:
                return known
        return None

    def _looks_cross_time(self, topic: str) -> bool:
        return any(keyword in topic for keyword in self.cross_time_keywords) and (
            "改革" in topic or "比较" in topic or "不同" in topic or "跨时空" in topic
        )

    @staticmethod
    def _normalize(raw_topic: str) -> str:
        return raw_topic.strip().strip("？?。.!！")
