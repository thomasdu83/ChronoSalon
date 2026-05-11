from __future__ import annotations

import json
from itertools import islice
from typing import Any

from chronosalon.catalog import is_moderator_name


class ReviewGenerator:
    """Generate a structured study review from room metadata and full chat history."""

    def __init__(self, model_client: Any | None = None) -> None:
        self.model_client = model_client

    def generate(
        self, room: dict[str, Any], messages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Build a study report that summarizes the whole conversation for the frontend."""
        title = room.get("room_title", "本次聊天室")
        characters = [
            item.get("name")
            for item in room.get("characters", [])
            if not is_moderator_name(item.get("name"))
        ]
        base_payload = {
            "room_title": title,
            "key_points": self._key_points_for(title),
            "character_positions": self._positions(characters),
            "misconceptions": self._misconceptions_for(title),
            "quiz_questions": self._quiz_for(title),
            "life_lessons": self._life_lessons_for(title, messages),
            "further_reflection": self._further_reflection_for(title, room, messages),
            "evidence_quotes": self._evidence_quotes(messages),
        }
        polished = self._llm_polish_payload(room, messages, base_payload)
        payload = polished or base_payload
        participant_count = len(characters)
        payload["study_report"] = {
            "title": f"{title} 学习回顾",
            "summary": payload.get("summary")
            or self._summary_for(title, room, messages),
            "meta": {
                "message_count": len(messages),
                "participant_count": participant_count,
                "room_type_label": "跨时空讨论"
                if room.get("room_type") == "cross_time"
                else "历史现场",
            },
            "sections": [
                {"title": "关键知识点", "items": payload["key_points"]},
                {
                    "title": "人物立场速览",
                    "items": self._position_highlights(payload["character_positions"]),
                },
                {"title": "为人处世的道理", "items": payload["life_lessons"]},
                {"title": "易错提醒", "items": payload["misconceptions"]},
                {"title": "值得继续思考", "items": payload["further_reflection"]},
            ],
        }
        payload["report_markdown"] = self._report_markdown(
            title=title,
            room=room,
            message_count=len(messages),
            key_points=payload["key_points"],
            character_positions=payload["character_positions"],
            life_lessons=payload["life_lessons"],
            misconceptions=payload["misconceptions"],
            further_reflection=payload["further_reflection"],
            evidence_quotes=payload["evidence_quotes"],
        )
        payload["message_count"] = len(messages)
        payload["report_source"] = "llm_enhanced" if polished else "deterministic"
        return payload

    def _llm_polish_payload(
        self,
        room: dict[str, Any],
        messages: list[dict[str, Any]],
        base_payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self.model_client or not self.model_client.is_available(
            "review_generator"
        ):
            return None
        content = self.model_client.complete(
            "review_generator",
            self._system_prompt(),
            self._user_prompt(room, messages, base_payload),
        )
        raw = self._extract_json_object(content)
        if not raw:
            return None

        merged = dict(base_payload)
        summary = str(raw.get("summary") or "").strip()
        if summary:
            merged["summary"] = summary

        for field in (
            "key_points",
            "life_lessons",
            "further_reflection",
            "misconceptions",
            "quiz_questions",
        ):
            cleaned = self._clean_list(raw.get(field))
            if cleaned:
                merged[field] = cleaned

        return merged

    @staticmethod
    def _system_prompt() -> str:
        return (
            "你是中学历史老师。请基于给定的聊天室信息、对话证据和本地骨架，"
            "输出一份更像老师评语的学习回顾。"
            "必须返回 JSON 对象，不要输出代码块，不要编造未在主题和对话中出现的事实。"
            "summary 要 1-2 句；key_points、life_lessons、further_reflection 各 2-4 条，"
            "语言要清晰、克制、适合学生复盘。"
        )

    def _user_prompt(
        self,
        room: dict[str, Any],
        messages: list[dict[str, Any]],
        base_payload: dict[str, Any],
    ) -> str:
        return json.dumps(
            {
                "room_title": room.get("room_title"),
                "room_type": room.get("room_type"),
                "topic_boundary": room.get("topic_boundary"),
                "learning_goals": room.get("learning_goals", []),
                "base_review": {
                    "summary": self._summary_for(
                        str(room.get("room_title") or "本次聊天室"), room, messages
                    ),
                    "key_points": base_payload["key_points"],
                    "life_lessons": base_payload["life_lessons"],
                    "further_reflection": base_payload["further_reflection"],
                    "misconceptions": base_payload["misconceptions"],
                    "quiz_questions": base_payload["quiz_questions"],
                },
                "evidence_quotes": base_payload["evidence_quotes"],
                "messages": self._compact_messages(messages),
                "output_schema": {
                    "summary": "string",
                    "key_points": ["string"],
                    "life_lessons": ["string"],
                    "further_reflection": ["string"],
                    "misconceptions": ["string"],
                    "quiz_questions": ["string"],
                },
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _compact_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        compact = []
        for message in messages[-10:]:
            sender = str(message.get("sender_name") or "").strip()
            content = str(message.get("content") or "").strip()
            if not sender or not content:
                continue
            compact.append({"sender_name": sender, "content": content[:160]})
        return compact

    @staticmethod
    def _extract_json_object(content: str | None) -> dict[str, Any] | None:
        if not content:
            return None
        normalized = content.strip()
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
    def _clean_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned = []
        for item in value:
            text = str(item or "").strip()
            if not text:
                continue
            cleaned.append(text)
        return cleaned[:4]

    @staticmethod
    def _key_points_for(title: str) -> list[str]:
        if "安史之乱" in title:
            return [
                "节度使权力膨胀削弱中央控制",
                "唐玄宗后期用人与政治判断出现问题",
                "个人野心与制度风险共同推动叛乱爆发",
            ]
        if "商鞅" in title:
            return [
                "商鞅变法削弱旧贵族特权",
                "军功爵制改变身份上升路径",
                "改革增强秦国实力但也带来严苛治理",
            ]
        if "改革" in title:
            return [
                "改革常触动既得利益",
                "君主支持和执行体系会影响改革成败",
                "比较改革要看时代条件，不能只看个人能力",
            ]
        return ["梳理事件背景", "比较人物立场", "分析原因与影响"]

    @staticmethod
    def _positions(characters: list[str | None]) -> dict[str, str]:
        mapping = {
            "安禄山": "强调朝廷猜忌和个人权力处境，也难以回避野心。",
            "李隆基": "承认信任与制衡失误，但会从皇权治理角度辩解。",
            "杨国忠": "强调中央防范边镇的必要性，同时存在个人争斗。",
            "商鞅": "主张法治、军功和富国强兵。",
            "旧贵族代表": "从既得利益受损角度反对改革。",
        }
        return {
            name: mapping.get(name, "围绕自身身份表达立场。")
            for name in characters
            if name
        }

    @staticmethod
    def _misconceptions_for(title: str) -> list[str]:
        if "安史之乱" in title:
            return [
                "不要把安史之乱简化成安禄山一个人的野心。",
                "不要忽视节度使制度和中央控制削弱。",
            ]
        if "商鞅" in title:
            return [
                "不要把变法只理解成商鞅个人性格强硬。",
                "旧贵族反对不是单纯愚昧，而是利益结构被改变。",
            ]
        return ["不要只用结果倒推过程。", "人物立场不等于完整史实。"]

    @staticmethod
    def _quiz_for(title: str) -> list[str]:
        if "安史之乱" in title:
            return [
                "节度使制度与安史之乱有什么关系？",
                "李隆基在安史之乱爆发前有哪些责任？",
                "如何同时理解个人野心和制度风险？",
            ]
        if "商鞅" in title:
            return [
                "旧贵族为什么反对商鞅变法？",
                "军功爵制为什么能增强秦国战斗力？",
                "商鞅变法的影响有哪些？",
            ]
        return [
            "这个事件的主要矛盾是什么？",
            "不同人物的立场为什么不同？",
            "这个事件对后来产生了什么影响？",
        ]

    @staticmethod
    def _life_lessons_for(title: str, messages: list[dict[str, Any]]) -> list[str]:
        lessons = []
        if "改革" in title or "变法" in title:
            lessons.extend(
                [
                    "推动改变时，要先看清会触动谁的利益，再决定推进节奏。",
                    "想做成大事，不能只有理想，还要建立支持者和执行路径。",
                ]
            )
        if "安史之乱" in title or "战争" in title:
            lessons.extend(
                [
                    "位高权重时更要接受监督，失去制衡会把局部风险放大成全局危机。",
                    "判断局势不能只听顺耳的话，越是在高位越要重视逆耳忠言。",
                ]
            )
        if not lessons:
            lessons.extend(
                [
                    "面对分歧时，先弄清各方真正担心什么，比急着站队更重要。",
                    "评价人物和事件时，要同时看动机、处境和后果，避免只凭情绪下结论。",
                ]
            )
        if len(messages) >= 4:
            lessons.append("一场有效讨论不是抢结论，而是让不同立场把理由说清楚。")
        return list(dict.fromkeys(lessons))[:3]

    def _further_reflection_for(
        self,
        title: str,
        room: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> list[str]:
        prompts = list(self._quiz_for(title))
        goals = ["如果把今天的主题换到另一个时代，哪些条件会改变结局？"]
        if room.get("room_type") == "cross_time":
            goals.append("跨时空人物的分歧里，哪些属于时代限制，哪些属于个人选择？")
        if len(messages) >= 3:
            goals.append("回看整段对话，哪一句最能代表核心矛盾？为什么？")
        prompts.extend(goals)
        return list(dict.fromkeys(prompts))[:4]

    @staticmethod
    def _summary_for(
        title: str,
        room: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> str:
        participant_count = len(
            [item for item in room.get("characters", []) if item.get("name")]
        )
        if messages:
            senders = [
                str(sender)
                for sender in dict.fromkeys(
                    message.get("sender_name")
                    for message in messages
                    if message.get("sender_name")
                )
            ]
            joined = "、".join(list(islice(senders, 0, 4)))
            return (
                f"本次围绕“{title}”的对话共整理出 {len(messages)} 条发言，"
                f"由 {joined} 等角色提供线索，帮助学生从多方立场理解主题。"
            )
        return (
            f"本次围绕“{title}”组织了 {participant_count} 位角色的学习房间，"
            "建议先生成更多对话，再形成更扎实的学习回顾。"
        )

    @staticmethod
    def _evidence_quotes(messages: list[dict[str, Any]]) -> list[str]:
        quotes: list[str] = []
        seen_senders: set[str] = set()
        for message in messages:
            sender = str(message.get("sender_name") or "").strip()
            content = str(message.get("content") or "").strip()
            if not sender or not content:
                continue
            if sender in seen_senders and len(quotes) >= 4:
                continue
            seen_senders.add(sender)
            snippet = content.replace("\n", " ").strip()
            if len(snippet) > 46:
                snippet = f"{snippet[:46]}..."
            quotes.append(f"{sender}：{snippet}")
            if len(quotes) >= 5:
                break
        return quotes

    @staticmethod
    def _position_highlights(character_positions: dict[str, str]) -> list[str]:
        highlights = []
        for name, position in character_positions.items():
            clean_name = str(name or "").strip()
            clean_position = str(position or "").strip()
            if not clean_name or not clean_position:
                continue
            highlights.append(f"{clean_name}：{clean_position}")
            if len(highlights) >= 4:
                break
        return highlights or ["不同人物会从各自处境出发解释同一事件。"]

    @staticmethod
    def _report_markdown(
        title: str,
        room: dict[str, Any],
        message_count: int,
        key_points: list[str],
        character_positions: dict[str, str],
        life_lessons: list[str],
        misconceptions: list[str],
        further_reflection: list[str],
        evidence_quotes: list[str],
    ) -> str:
        lines = [
            f"# {title} 学习回顾",
            "",
            f"- 聊天室类型：{'跨时空讨论' if room.get('room_type') == 'cross_time' else '历史现场'}",
            f"- 主题边界：{room.get('topic_boundary') or '未提供'}",
            f"- 对话轮次摘要：共参考 {message_count} 条发言，摘录其中的关键证据。",
            "",
            "## 关键知识点",
            *[f"- {item}" for item in key_points],
            "",
            "## 人物立场速览",
            *[
                f"- {item}"
                for item in ReviewGenerator._position_highlights(character_positions)
            ],
            "",
            "## 为人处世的道理",
            *[f"- {item}" for item in life_lessons],
            "",
            "## 易错提醒",
            *[f"- {item}" for item in misconceptions],
            "",
            "## 值得继续思考",
            *[f"- {item}" for item in further_reflection],
            "",
        ]
        return "\n".join(lines)
