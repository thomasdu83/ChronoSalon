from pathlib import Path

from chronosalon.app import ChronoSalonApp
from chronosalon.services.config_loader import ModelConfigLoader
from chronosalon.services.review_generator import ReviewGenerator


ROOT = Path(__file__).resolve().parents[1]


def test_review_generator_returns_study_artifacts():
    app = ChronoSalonApp()
    room = app.build_room("安史之乱")
    chat = app.chat(room, "@安禄山 你为什么起兵？")
    review = app.review(room, chat["messages"])

    assert review["room_title"] == "安史之乱"
    assert len(review["key_points"]) >= 3
    assert "安禄山" in review["character_positions"]
    assert any("节度使" in question for question in review["quiz_questions"])
    assert len(review["life_lessons"]) >= 2
    assert len(review["further_reflection"]) >= 2
    assert "## 关键知识点" in review["report_markdown"]
    assert "## 人物立场速览" in review["report_markdown"]
    assert "## 为人处世的道理" in review["report_markdown"]
    assert "## 易错提醒" in review["report_markdown"]
    assert "## 值得继续思考" in review["report_markdown"]
    assert "## 对话依据" not in review["report_markdown"]
    assert review["study_report"]["sections"][0]["title"] == "关键知识点"
    assert review["study_report"]["sections"][1]["title"] == "人物立场速览"
    assert review["study_report"]["meta"]["message_count"] == len(chat["messages"])


def test_model_config_template_loads_roles():
    config_path = ROOT / "src" / "config" / "model_config.yaml"
    configs = ModelConfigLoader().load(config_path)

    assert {
        "room_builder",
        "orchestrator",
        "character_responder",
        "moderator",
        "review_generator",
    }.issubset(configs)
    assert configs["room_builder"].api_key_env == "KIMI_API_KEY"
    assert (
        configs["character_responder"].temperature > configs["orchestrator"].temperature
    )


def test_app_end_to_end_for_shang_yang():
    app = ChronoSalonApp()
    room = app.build_room("商鞅变法")
    chat = app.chat(room, "@商鞅 变法主要改了什么？")
    review = app.review(room, chat["messages"])

    assert room["room_type"] == "historical_scene"
    assert chat["messages"][0]["sender_name"] == "商鞅"
    assert "旧贵族代表" in review["character_positions"]


def test_review_generator_uses_all_round_messages_in_evidence():
    app = ChronoSalonApp()
    room = app.build_room("为什么改革总是困难？", room_type="cross_time")
    opening = app.chat(room, "开场")
    turn_one = app.chat(opening["room"], "@商鞅 改革为什么难？", opening["messages"])
    full_messages = [*opening["messages"], *turn_one["messages"]]

    review = app.review(turn_one["room"], full_messages)

    evidence_text = " ".join(review["evidence_quotes"])
    assert "群主" in evidence_text
    assert "商鞅" in evidence_text
    assert review["message_count"] == len(full_messages)


def test_review_generator_uses_llm_polish_when_available():
    class FakeModelClient:
        def is_available(self, role: str) -> bool:
            return role == "review_generator"

        def complete(
            self, role: str, system_prompt: str, user_prompt: str, timeout: float = 25.0
        ) -> str | None:
            return """
            {
              "summary": "这份回顾强调制度风险、人物选择与时代条件三条主线。",
              "key_points": ["节度使坐大是叛乱爆发的结构性前提。", "君主识人与制衡失误会放大边镇风险。", "个人野心与制度漏洞是在同一时刻叠加爆发的。"],
              "life_lessons": ["身居高位时更要主动接受监督。", "做判断不能只听顺耳的话。", "重大决策前要提前识别制度漏洞。"],
              "further_reflection": ["如果没有节度使体制，这场危机会如何变化？", "个人能力和制度约束，哪一个更决定历史走向？", "今天的组织治理里有没有类似风险？"]
            }
            """

    room = ChronoSalonApp().build_room("安史之乱")
    messages = [
        {
            "sender_name": "群主",
            "content": "今天先看制度风险。",
            "sender_type": "moderator",
        },
        {
            "sender_name": "安禄山",
            "content": "边镇权力坐大之后，很多事已不受控制。",
            "sender_type": "character",
        },
    ]

    review = ReviewGenerator(FakeModelClient()).generate(room, messages)

    assert review["study_report"]["summary"].startswith("这份回顾强调制度风险")
    assert review["key_points"][0] == "节度使坐大是叛乱爆发的结构性前提。"
    assert review["life_lessons"][0] == "身居高位时更要主动接受监督。"
    assert review["report_source"] == "llm_enhanced"


def test_review_generator_falls_back_when_llm_payload_is_invalid():
    class BadModelClient:
        def is_available(self, role: str) -> bool:
            return role == "review_generator"

        def complete(
            self, role: str, system_prompt: str, user_prompt: str, timeout: float = 25.0
        ) -> str | None:
            return "不是 JSON"

    room = ChronoSalonApp().build_room("商鞅变法")
    review = ReviewGenerator(BadModelClient()).generate(room, [])

    assert review["report_source"] == "deterministic"
    assert review["key_points"][0] == "商鞅变法削弱旧贵族特权"
