from chronosalon.catalog import moderator_character
from chronosalon.models import RoomDraft
from chronosalon.services.room_builder import RoomBuilder


class StubTopicIntelligence:
    def __init__(self, draft: RoomDraft | None) -> None:
        self.draft = draft
        self.calls: list[tuple[str, str | None]] = []

    def build(self, topic: str, room_type: str | None = None) -> RoomDraft | None:
        self.calls.append((topic, room_type))
        return self.draft


def test_build_known_historical_scene_room():
    room = RoomBuilder().build("安史之乱").to_dict()

    assert room["status"] == "ready"
    assert room["room_type"] == "historical_scene"
    assert room["room_title"] == "安史之乱"
    names = [item["name"] for item in room["characters"]]
    assert names[:4] == ["群主", "安禄山", "李隆基", "杨国忠"]
    assert "节度使权力为什么会变得这么大？" in room["recommended_questions"]


def test_big_topic_requires_choice():
    room = RoomBuilder().build("唐朝").to_dict()

    assert room["status"] == "needs_choice"
    assert room["room_type"] is None
    assert "安史之乱" in room["options"]


def test_person_topic_requires_choice():
    room = RoomBuilder().build("秦始皇").to_dict()

    assert room["status"] == "needs_choice"
    assert "秦始皇统一六国" in room["options"]


def test_cross_time_reform_room():
    room = RoomBuilder().build("为什么改革总是困难？").to_dict()

    assert room["status"] == "ready"
    assert room["room_type"] == "cross_time"
    assert "改革" in room["room_title"]
    names = [item["name"] for item in room["characters"]]
    assert {"商鞅", "王安石", "张居正", "康有为"}.issubset(names)
    assert "改革目标" in room["comparison_dimensions"]
    assert any("假想" in rule for rule in room["simulation_rules"])


def test_can_force_cross_time_room_type_for_specific_topic():
    room = RoomBuilder().build("安史之乱", room_type="cross_time").to_dict()

    assert room["status"] == "ready"
    assert room["room_type"] == "cross_time"
    assert "跨时空" in room["topic_boundary"]
    assert "时代背景" in room["comparison_dimensions"]


def test_unknown_supported_historical_event_builds_minimum_viable_room():
    room = RoomBuilder().build("戊戌变法").to_dict()

    assert room["status"] == "ready"
    assert room["room_type"] == "historical_scene"
    assert room["time_range"]
    assert room["scene_allowed_eras"]
    assert len(room["characters"]) >= 4
    assert [item["name"] for item in room["characters"]].count("群主") == 1
    assert len([item for item in room["characters"] if item["name"] != "群主"]) >= 3
    assert len(room["recommended_questions"]) >= 3
    assert any(question.startswith("@") for question in room["recommended_questions"])


def test_unrecognized_topic_does_not_create_empty_ready_room():
    room = RoomBuilder().build("火星税制大讨论").to_dict()

    assert room["status"] == "needs_choice"
    assert room["room_type"] is None
    assert room["characters"] == []
    assert room["options"]


def test_historical_scene_room_requires_time_boundary_and_scene_eras():
    room = RoomBuilder().build("戊戌变法").to_dict()

    assert room["status"] == "ready"
    assert room["room_type"] == "historical_scene"
    assert room["time_range"]
    assert room["scene_allowed_eras"] == ["晚清"]


def test_llm_topic_intelligence_can_build_ready_room_after_local_rules_fail():
    intelligence = StubTopicIntelligence(
        RoomDraft(
            status="ready",
            room_title="巴黎公社",
            room_type="historical_scene",
            topic_boundary="围绕巴黎公社的起因、参与者、镇压和影响展开。",
            time_range="近代法国，1871年前后",
            learning_goals=["理解背景", "比较立场", "分析影响"],
            characters=[
                moderator_character(),
                {"name": "公社成员代表", "type": "group_character", "era": "近代法国"},
                {"name": "法国政府代表", "type": "group_character", "era": "近代法国"},
                {"name": "巴黎市民代表", "type": "group_character", "era": "近代法国"},
            ],
            recommended_questions=[
                "@公社成员代表 你们为何要接管巴黎？",
                "@法国政府代表 你们为何选择镇压？",
                "@巴黎市民代表 这场事件怎样影响了你们？",
            ],
            source_pack_query=["巴黎公社", "巴黎公社 背景", "巴黎公社 影响"],
            scene_allowed_eras=["近代法国"],
        )
    )
    room = RoomBuilder(topic_intelligence=intelligence).build("巴黎公社").to_dict()

    assert room["status"] == "ready"
    assert room["room_title"] == "巴黎公社"
    assert room["scene_allowed_eras"] == ["近代法国"]
    assert intelligence.calls == [("巴黎公社", None)]


def test_llm_topic_intelligence_output_must_pass_validator():
    intelligence = StubTopicIntelligence(
        RoomDraft(
            status="ready",
            room_title="巴黎公社",
            room_type="historical_scene",
            topic_boundary="围绕巴黎公社展开。",
            time_range="",
            learning_goals=["理解背景"],
            characters=[moderator_character()],
            recommended_questions=["这是什么？"],
            source_pack_query=["巴黎公社"],
            scene_allowed_eras=[],
        )
    )
    room = RoomBuilder(topic_intelligence=intelligence).build("巴黎公社").to_dict()

    assert room["status"] == "needs_choice"
    assert room["room_type"] is None
    assert "历史人物或群体角色不足 3 个" in room["topic_boundary"]


def test_historical_scene_rejects_obvious_era_conflict_in_characters():
    intelligence = StubTopicIntelligence(
        RoomDraft(
            status="ready",
            room_title="巴黎公社扩展讨论",
            room_type="historical_scene",
            topic_boundary="围绕巴黎公社的起因与影响展开。",
            time_range="近代法国，1871年前后",
            learning_goals=["理解背景", "比较立场", "分析影响"],
            characters=[
                moderator_character(),
                {"name": "公社成员代表", "type": "group_character", "era": "近代法国"},
                {"name": "秦始皇", "type": "core_character", "era": "秦朝"},
                {"name": "巴黎市民代表", "type": "group_character", "era": "近代法国"},
            ],
            recommended_questions=[
                "@公社成员代表 你们为何要接管巴黎？",
                "@秦始皇 你怎么看巴黎公社？",
                "@巴黎市民代表 这场事件如何影响了你们？",
            ],
            source_pack_query=["巴黎公社", "巴黎公社 背景"],
            scene_allowed_eras=["近代法国"],
        )
    )

    room = (
        RoomBuilder(topic_intelligence=intelligence).build("巴黎公社扩展讨论").to_dict()
    )

    assert room["status"] == "needs_choice"
    assert room["room_type"] is None
    assert "时代冲突" in room["topic_boundary"]
