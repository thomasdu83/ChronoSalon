from pathlib import Path

from chronosalon.services.llm_client import OpenAICompatibleModelClient
from chronosalon.services.topic_intelligence import TopicIntelligence


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / ".test_tmp"


def build_client_with_room_builder_model() -> OpenAICompatibleModelClient:
    TMP.mkdir(exist_ok=True)
    config = TMP / "topic_intelligence_model_config.yaml"
    env = TMP / ".env.topic_intelligence"
    config.write_text(
        """
models:
  room_builder:
    provider: "test"
    model_name: "test-model"
    api_key_env: "CHRONOSALON_TOPIC_INTELLIGENCE_KEY"
    base_url: "https://example.invalid/v1"
    temperature: 0.5
    max_tokens: 800
""",
        encoding="utf-8",
    )
    env.write_text(
        "CHRONOSALON_TOPIC_INTELLIGENCE_KEY=secret-value\n", encoding="utf-8"
    )
    return OpenAICompatibleModelClient(config, env)


def test_topic_intelligence_normalizes_valid_ready_payload(monkeypatch):
    client = build_client_with_room_builder_model()
    intelligence = TopicIntelligence(client)

    monkeypatch.setattr(
        client,
        "complete",
        lambda *args, **kwargs: """
        {
          "status": "ready",
          "room_title": "巴黎公社",
          "room_type": "historical_scene",
          "topic_boundary": "围绕巴黎公社的起因、参与者、镇压和影响展开。",
          "time_range": "近代法国，1871年前后",
          "learning_goals": ["理解背景", "比较立场", "分析影响"],
          "characters": [
            {"name": "公社成员代表", "type": "group_character", "era": "近代法国", "identity": "巴黎公社参与者", "role": "支持公社"},
            {"name": "法国政府代表", "type": "group_character", "era": "近代法国", "identity": "法国政府力量", "role": "反对公社"},
            {"name": "巴黎市民代表", "type": "group_character", "era": "近代法国", "identity": "巴黎普通市民", "role": "承受局势变化"}
          ],
          "recommended_questions": [
            "@公社成员代表 你们为何要接管巴黎？",
            "@法国政府代表 你们为何选择镇压？",
            "@巴黎市民代表 这场事件怎样影响了你们？"
          ],
          "source_pack_query": ["巴黎公社", "巴黎公社 背景", "巴黎公社 影响"],
          "scene_allowed_eras": ["近代法国"]
        }
        """,
    )

    room = intelligence.build("巴黎公社")

    assert room is not None
    payload = room.to_dict()
    assert payload["status"] == "ready"
    assert payload["room_type"] == "historical_scene"
    assert payload["characters"][0]["name"] == "群主"
    assert payload["scene_allowed_eras"] == ["近代法国"]


def test_topic_intelligence_rejects_invalid_json(monkeypatch):
    client = build_client_with_room_builder_model()
    intelligence = TopicIntelligence(client)
    monkeypatch.setattr(client, "complete", lambda *args, **kwargs: "not json")

    room = intelligence.build("巴黎公社")

    assert room is None


def test_topic_intelligence_rejects_room_type_mismatch(monkeypatch):
    client = build_client_with_room_builder_model()
    intelligence = TopicIntelligence(client)
    monkeypatch.setattr(
        client,
        "complete",
        lambda *args, **kwargs: """
        {
          "status": "ready",
          "room_title": "巴黎公社",
          "room_type": "cross_time",
          "topic_boundary": "围绕巴黎公社展开。",
          "time_range": "近代法国，1871年前后",
          "characters": [
            {"name": "公社成员代表", "type": "group_character", "era": "近代法国"},
            {"name": "法国政府代表", "type": "group_character", "era": "近代法国"},
            {"name": "巴黎市民代表", "type": "group_character", "era": "近代法国"}
          ],
          "recommended_questions": [
            "@公社成员代表 你们为何要接管巴黎？",
            "@法国政府代表 你们为何选择镇压？",
            "@巴黎市民代表 这场事件怎样影响了你们？"
          ]
        }
        """,
    )

    room = intelligence.build("巴黎公社", room_type="historical_scene")

    assert room is None


def test_topic_intelligence_needs_choice_without_options_gets_default_suggestions(
    monkeypatch,
):
    client = build_client_with_room_builder_model()
    intelligence = TopicIntelligence(client)
    monkeypatch.setattr(
        client,
        "complete",
        lambda *args, **kwargs: """
        {
          "status": "needs_choice",
          "room_title": "KPL总决赛",
          "room_type": null,
          "topic_boundary": "这个主题有点大，建议先聚焦一个具体方向。"
        }
        """,
    )

    room = intelligence.build("KPL总决赛")

    assert room is not None
    payload = room.to_dict()
    assert payload["status"] == "needs_choice"
    assert payload["room_type"] is None
    assert payload["characters"] == []
    assert payload["options"]
    assert "KPL总决赛 背景" in payload["options"]
