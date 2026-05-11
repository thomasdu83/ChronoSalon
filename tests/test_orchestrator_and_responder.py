from chronosalon.services.orchestrator import Orchestrator
from chronosalon.services.responder import HybridRoleplayResponder, run_speaking_plan
from chronosalon.services.room_builder import RoomBuilder


def test_orchestrator_prioritizes_mentioned_character_only():
    room = RoomBuilder().build("安史之乱").to_dict()
    plan = Orchestrator().plan(room, "@安禄山 胖子你出来讲讲吧，为啥叛乱？")

    assert plan.intent == "ask_character"
    assert plan.target_character == "安禄山"
    assert [step.speaker for step in plan.speaker_sequence] == ["安禄山"]
    assert plan.max_auto_messages == 1


def test_responder_runs_single_mentioned_character_reply():
    room = RoomBuilder().build("安史之乱").to_dict()
    plan = Orchestrator().plan(room, "@安禄山 你为什么起兵？")
    messages = run_speaking_plan(room, plan, "@安禄山 你为什么起兵？")

    assert len(messages) == 1
    assert messages[0]["sender_name"] == "安禄山"
    assert "野心" in messages[0]["content"]


def test_cross_time_mention_does_not_auto_append_moderator():
    room = RoomBuilder().build("安史之乱", room_type="cross_time").to_dict()
    plan = Orchestrator().plan(room, "@拿破仑 你遇到这种情况怎么办？")

    assert plan.intent == "ask_character"
    assert plan.target_character == "拿破仑"
    assert [step.speaker for step in plan.speaker_sequence] == ["拿破仑"]


def test_mention_everyone_targets_existing_room_characters():
    room = RoomBuilder().build("安史之乱").to_dict()
    plan = Orchestrator().plan(room, "@所有人 你们怎么看这件事？")

    assert plan.intent == "ask_everyone"
    assert plan.target_character == "所有人"
    assert [step.speaker for step in plan.speaker_sequence] == ["安禄山", "李隆基", "杨国忠", "边镇士兵代表"]
    assert "群主" not in [step.speaker for step in plan.speaker_sequence]


def test_concept_question_pauses_for_moderator():
    room = RoomBuilder().build("安史之乱").to_dict()
    plan = Orchestrator().plan(room, "等一下，节度使是什么意思？")

    assert plan.intent == "explain_concept"
    assert len(plan.speaker_sequence) == 1
    assert plan.speaker_sequence[0].speaker == "群主"


def test_general_message_is_first_handled_by_group_owner():
    room = RoomBuilder().build("安史之乱").to_dict()
    opening = Orchestrator().plan(room, "开场")
    plan = Orchestrator().plan(room, "这是不是皇帝的问题？", [{"sender_name": "群主", "content": "开场"}])

    assert opening.speaker_sequence[0].speaker == "群主"
    assert plan.intent == "general_question"
    assert plan.target_character == "群主"
    assert [step.speaker for step in plan.speaker_sequence] == ["群主"]
    assert plan.max_auto_messages == 1


def test_cross_time_opening_is_moderator_only():
    room = RoomBuilder().build("为什么改革总是困难？").to_dict()
    plan = Orchestrator().plan(room, "开场")
    messages = run_speaking_plan(room, plan, "开场")

    assert plan.intent == "opening"
    assert [step.speaker for step in plan.speaker_sequence] == ["群主"]
    assert plan.max_auto_messages == 1
    assert len(messages) == 1
    assert messages[0]["sender_name"] == "群主"


def test_group_owner_connects_history_with_life_lessons_without_extra_speakers():
    room = RoomBuilder().build("安史之乱").to_dict()
    plan = Orchestrator().plan(room, "百姓苦啊", [{"sender_name": "群主", "content": "开场"}])
    messages = run_speaking_plan(room, plan, "百姓苦啊")

    assert [step.speaker for step in plan.speaker_sequence] == ["群主", "边镇士兵代表"]
    assert len(messages) == 2
    assert messages[0]["sender_name"] == "群主"
    assert messages[1]["sender_name"] == "边镇士兵代表"
    assert "普通人" in messages[0]["content"]
    assert "代价" in messages[0]["content"]


def test_character_responder_receives_recent_context():
    room = RoomBuilder().build("安史之乱").to_dict()
    room["characters"].append(
        {
            "name": "杜甫",
            "type": "temporary_character",
            "role": "经历战乱的诗人视角",
            "is_temporary": True,
        }
    )
    plan = Orchestrator().plan(room, "@杜甫 你怎么看？")
    messages = run_speaking_plan(
        room,
        plan,
        "@杜甫 你怎么看？",
        [{"sender_name": "群主", "sender_type": "moderator", "content": "下一步可以@杜甫听百姓视角。"}],
    )

    assert messages[0]["sender_name"] == "杜甫"
    assert "接着群主刚才的话说" in messages[0]["content"]


def test_orchestrator_appends_conflicting_followup_for_targeted_question():
    room = RoomBuilder().build("安史之乱").to_dict()
    plan = Orchestrator().plan(
        room,
        "@安禄山 你是不是被杨国忠逼反的？",
        [{"sender_name": "群主", "sender_type": "moderator", "content": "先说清楚是谁先失控。"}],
    )

    assert plan.intent == "ask_character"
    assert [step.speaker for step in plan.speaker_sequence] == ["安禄山", "杨国忠"]
    assert plan.max_auto_messages == 2


class MisalignedModelClient:
    def is_available(self, role):
        return True

    def complete(self, role, system_prompt, user_prompt):
        return "@杜甫 杜工部，你当时在长安城外，应该看到了不少惨状吧？你来评评。"


def test_hybrid_responder_falls_back_when_llm_turns_speaker_into_addressee():
    room = RoomBuilder().build("安史之乱").to_dict()
    room["characters"].append(
        {
            "name": "杜甫",
            "type": "temporary_character",
            "role": "经历战乱的诗人视角",
            "is_temporary": True,
        }
    )

    responder = HybridRoleplayResponder(MisalignedModelClient())
    message = responder.respond("杜甫", "用第一人称回应学生。", room, "@杜甫 你怎么看？").to_dict()

    assert message["sender_name"] == "杜甫"
    assert "@杜甫" not in message["content"]
    assert "战乱" in message["content"]
