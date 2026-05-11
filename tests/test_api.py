from fastapi.testclient import TestClient

import chronosalon.api as api_module
from chronosalon.api import create_api_app
from chronosalon.models import RoomDraft


def test_health_endpoint():
    client = TestClient(create_api_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_build_room_endpoint():
    client = TestClient(create_api_app())

    response = client.post("/api/rooms/build", json={"topic": "安史之乱"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["room_title"] == "安史之乱"
    assert payload["room_type"] == "historical_scene"


def test_build_cross_time_room_endpoint():
    client = TestClient(create_api_app())

    response = client.post(
        "/api/rooms/build", json={"topic": "安史之乱", "room_type": "cross_time"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["room_type"] == "cross_time"


def test_build_room_endpoint_for_supported_unknown_event_is_not_empty_room():
    client = TestClient(create_api_app())

    response = client.post("/api/rooms/build", json={"topic": "戊戌变法"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["room_type"] == "historical_scene"
    assert len(payload["characters"]) >= 4
    assert payload["time_range"]


def test_build_room_endpoint_for_unrecognized_topic_returns_needs_choice():
    client = TestClient(create_api_app())

    response = client.post("/api/rooms/build", json={"topic": "火星税制大讨论"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_choice"
    assert payload["room_type"] is None
    assert payload["characters"] == []


def test_build_room_endpoint_uses_topic_intelligence_when_available():
    draft = RoomDraft(
        status="ready",
        room_title="巴黎公社",
        room_type="historical_scene",
        topic_boundary="围绕巴黎公社的起因、参与者、镇压和影响展开。",
        time_range="近代法国，1871年前后",
        learning_goals=["理解背景", "比较立场", "分析影响"],
        characters=[
            {"name": "群主", "type": "moderator", "era": "现代"},
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
    client = TestClient(
        create_api_app(
            topic_intelligence=type(
                "TI", (), {"build": lambda self, topic, room_type=None: draft}
            )()
        )
    )

    response = client.post("/api/rooms/build", json={"topic": "巴黎公社"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["room_title"] == "巴黎公社"
    assert payload["scene_allowed_eras"] == ["近代法国"]


def test_build_room_endpoint_uses_default_topic_intelligence_when_not_injected(monkeypatch):
    fake_topic_intelligence = object()

    class FakeChronoSalonApp:
        instances = []

        def __init__(
            self,
            use_llm=False,
            config_path=None,
            env_path=None,
            topic_intelligence=None,
        ):
            self.use_llm = use_llm
            self.topic_intelligence = topic_intelligence
            self.__class__.instances.append(self)

        def build_room(self, topic, room_type=None):
            return {
                "status": "ready" if self.topic_intelligence is fake_topic_intelligence else "needs_choice",
                "room_title": topic,
                "room_type": "historical_scene" if self.topic_intelligence is fake_topic_intelligence else None,
                "topic_boundary": "ok" if self.topic_intelligence is fake_topic_intelligence else "missing",
                "characters": [],
                "time_range": "",
                "scene_allowed_eras": [],
            }

        def chat(self, room, message, recent_messages=None):
            return {}

        def plan_chat(self, room, message, recent_messages=None):
            return {}

        def review(self, room, messages):
            return {}

    monkeypatch.setattr(api_module, "ChronoSalonApp", FakeChronoSalonApp)
    monkeypatch.setattr(api_module, "build_default_topic_intelligence", lambda: fake_topic_intelligence, raising=False)

    client = TestClient(api_module.create_api_app())
    response = client.post("/api/rooms/build", json={"topic": "巴黎公社"})

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert len(FakeChronoSalonApp.instances) >= 2
    assert FakeChronoSalonApp.instances[0].topic_intelligence is fake_topic_intelligence


def test_chat_endpoint_with_local_fallback():
    client = TestClient(create_api_app())
    room = client.post("/api/rooms/build", json={"topic": "安史之乱"}).json()

    response = client.post(
        "/api/chat",
        json={
            "room": room,
            "message": "@安禄山 你为什么起兵？",
            "recent_messages": [],
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["target_character"] == "安禄山"
    assert payload["messages"][0]["sender_name"] == "安禄山"
    assert len(payload["messages"]) == 1


def test_chat_plan_endpoint_returns_speakers_before_generation():
    client = TestClient(create_api_app())
    room = client.post("/api/rooms/build", json={"topic": "安史之乱"}).json()

    response = client.post(
        "/api/chat/plan",
        json={
            "room": room,
            "message": "@安禄山 你为什么起兵？",
            "recent_messages": [],
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["speaker_sequence"][0]["speaker"] == "安禄山"
    assert len(payload["plan"]["speaker_sequence"]) == 1
    assert "messages" not in payload


def test_cross_time_opening_chat_returns_only_moderator_message():
    client = TestClient(create_api_app())
    room = client.post(
        "/api/rooms/build",
        json={"topic": "为什么改革总是困难？", "room_type": "cross_time"},
    ).json()

    response = client.post(
        "/api/chat",
        json={
            "room": room,
            "message": "开场",
            "recent_messages": [],
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["intent"] == "opening"
    assert [item["speaker"] for item in payload["plan"]["speaker_sequence"]] == ["群主"]
    assert len(payload["messages"]) == 1
    assert payload["messages"][0]["sender_name"] == "群主"


def test_chat_plan_everyone_does_not_create_everyone_character():
    client = TestClient(create_api_app())
    room = client.post("/api/rooms/build", json={"topic": "安史之乱"}).json()

    response = client.post(
        "/api/chat/plan",
        json={
            "room": room,
            "message": "@所有人 你们怎么看这件事？",
            "recent_messages": [],
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["added_character"] is None
    assert payload["plan"]["intent"] == "ask_everyone"
    assert "所有人" not in [item["name"] for item in payload["room"]["characters"]]
    assert payload["plan"]["speaker_sequence"][0]["speaker"] == "安禄山"


def test_chat_endpoint_temporarily_adds_missing_same_scene_character():
    client = TestClient(create_api_app())
    room = client.post("/api/rooms/build", json={"topic": "安史之乱"}).json()

    response = client.post(
        "/api/chat",
        json={
            "room": room,
            "message": "@杜甫 你看到的战乱是什么样？",
            "recent_messages": [],
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["added_character"]["name"] == "杜甫"
    assert any(item["name"] == "杜甫" for item in payload["room"]["characters"])
    assert payload["messages"][0]["sender_name"] == "杜甫"


def test_temporary_character_stays_in_room_after_joining():
    client = TestClient(create_api_app())
    room = client.post("/api/rooms/build", json={"topic": "安史之乱"}).json()

    first_turn = client.post(
        "/api/chat",
        json={
            "room": room,
            "message": "@杜甫 你看到的战乱是什么样？",
            "recent_messages": [],
            "use_llm": False,
        },
    ).json()

    second_turn = client.post(
        "/api/chat/plan",
        json={
            "room": first_turn["room"],
            "message": "@杜甫 你再补一句。",
            "recent_messages": first_turn["messages"],
            "use_llm": False,
        },
    ).json()

    assert second_turn["added_character"] is None
    assert any(item["name"] == "杜甫" for item in second_turn["room"]["characters"])
    assert second_turn["plan"]["target_character"] == "杜甫"


def test_everyone_mentions_include_temporary_characters_after_joining():
    client = TestClient(create_api_app())
    room = client.post("/api/rooms/build", json={"topic": "安史之乱"}).json()

    joined = client.post(
        "/api/chat",
        json={
            "room": room,
            "message": "@杜甫 你看到的战乱是什么样？",
            "recent_messages": [],
            "use_llm": False,
        },
    ).json()

    plan = client.post(
        "/api/chat/plan",
        json={
            "room": joined["room"],
            "message": "@所有人 你们怎么看？",
            "recent_messages": joined["messages"],
            "use_llm": False,
        },
    ).json()

    speakers = [item["speaker"] for item in plan["plan"]["speaker_sequence"]]
    assert "杜甫" in speakers


def test_chat_endpoint_blocks_out_of_scene_character():
    client = TestClient(create_api_app())
    room = client.post("/api/rooms/build", json={"topic": "安史之乱"}).json()

    response = client.post(
        "/api/chat",
        json={
            "room": room,
            "message": "@秦始皇 你怎么看安史之乱？",
            "recent_messages": [],
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["blocked_reason"]
    assert payload["messages"][0]["sender_name"] == "群主"
    assert "跨时空讨论" in payload["messages"][0]["content"]


def test_chat_endpoint_blocks_unverified_character_in_historical_scene():
    client = TestClient(create_api_app())
    room = client.post("/api/rooms/build", json={"topic": "安史之乱"}).json()

    response = client.post(
        "/api/chat",
        json={
            "room": room,
            "message": "@刘备 你怎么看安史之乱？",
            "recent_messages": [],
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["added_character"] is None
    assert payload["blocked_reason"]
    assert "不能直接放进历史现场" in payload["messages"][0]["content"]
    assert "跨时空讨论" in payload["messages"][0]["content"]
    assert "刘备" not in [item["name"] for item in payload["room"]["characters"]]


def test_chat_endpoint_blocks_later_out_of_scene_mention_too():
    client = TestClient(create_api_app())
    room = client.post("/api/rooms/build", json={"topic": "安史之乱"}).json()

    response = client.post(
        "/api/chat/plan",
        json={
            "room": room,
            "message": "@安禄山 你能不能和 @秦始皇 比较一下？",
            "recent_messages": [],
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["added_character"] is None
    assert payload["blocked_reason"]
    assert payload["plan"]["intent"] == "blocked_cross_time_mention"
    assert "秦始皇" in payload["blocked_reason"]
    assert "跨时空讨论" in payload["blocked_reason"]


def test_unmentioned_student_message_gets_group_owner_then_mentioned_followup():
    client = TestClient(create_api_app())
    room = client.post("/api/rooms/build", json={"topic": "安史之乱"}).json()
    opening = client.post(
        "/api/chat",
        json={
            "room": room,
            "message": "开场",
            "recent_messages": [],
            "use_llm": False,
        },
    ).json()

    response = client.post(
        "/api/chat",
        json={
            "room": room,
            "message": "百姓苦啊",
            "recent_messages": opening["messages"],
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["intent"] == "general_question"
    assert [item["speaker"] for item in payload["plan"]["speaker_sequence"]] == ["群主", "边镇士兵代表"]
    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["sender_name"] == "群主"
    assert payload["messages"][1]["sender_name"] == "边镇士兵代表"
    assert "群主" in payload["messages"][1]["content"]
    assert "代价" in payload["messages"][0]["content"]


def test_targeted_question_adds_single_conflicting_followup_without_duplication():
    client = TestClient(create_api_app())
    room = client.post("/api/rooms/build", json={"topic": "安史之乱"}).json()

    response = client.post(
        "/api/chat",
        json={
            "room": room,
            "message": "@安禄山 你是不是被杨国忠逼反的？",
            "recent_messages": [{"sender_name": "群主", "sender_type": "moderator", "content": "先说清楚是谁先失控。"}],
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["speaker"] for item in payload["plan"]["speaker_sequence"]] == ["安禄山", "杨国忠"]
    assert [item["sender_name"] for item in payload["messages"]] == ["安禄山", "杨国忠"]


def test_review_endpoint():
    client = TestClient(create_api_app())
    room = client.post("/api/rooms/build", json={"topic": "商鞅变法"}).json()
    chat = client.post(
        "/api/chat",
        json={
            "room": room,
            "message": "@商鞅 变法主要改了什么？",
            "recent_messages": [],
            "use_llm": False,
        },
    ).json()

    response = client.post(
        "/api/review", json={"room": room, "messages": chat["messages"]}
    )

    assert response.status_code == 200
    payload = response.json()
    assert "key_points" in payload
    assert "life_lessons" in payload
    assert "further_reflection" in payload
    assert "report_markdown" in payload
    assert payload["study_report"]["sections"][1]["title"] == "为人处世的道理"


def test_review_endpoint_prefers_llm_review_app_when_available(monkeypatch):
    class FakeChronoSalonApp:
        instances = []

        def __init__(
            self,
            use_llm=False,
            config_path=None,
            env_path=None,
            topic_intelligence=None,
        ):
            self.use_llm = use_llm
            self.__class__.instances.append(self)

        def build_room(self, topic, room_type=None):
            return {"room_title": topic, "room_type": "historical_scene"}

        def chat(self, room, message, recent_messages=None):
            return {}

        def plan_chat(self, room, message, recent_messages=None):
            return {}

        def review(self, room, messages):
            return {
                "study_report": {
                    "title": "LLM 学习回顾" if self.use_llm else "本地学习回顾",
                    "summary": "ok",
                    "sections": [],
                },
                "report_source": "llm_enhanced" if self.use_llm else "deterministic",
            }

    monkeypatch.setattr(api_module, "ChronoSalonApp", FakeChronoSalonApp)

    client = TestClient(api_module.create_api_app())
    response = client.post(
        "/api/review",
        json={"room": {"room_title": "安史之乱"}, "messages": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["study_report"]["title"] == "LLM 学习回顾"
    assert payload["report_source"] == "llm_enhanced"
