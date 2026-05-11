from __future__ import annotations

from typing import Any

from chronosalon.catalog import MODERATOR_NAME, is_moderator_name
from chronosalon.models import OrchestrationPlan, SpeakerStep
from chronosalon.services.character_manager import extract_mentions


class Orchestrator:
    """Turns a student message into a short group-chat speaking plan."""

    def plan(self, room: dict[str, Any], user_message: str, recent_messages: list[dict] | None = None) -> OrchestrationPlan:
        recent_messages = recent_messages or []
        target = self._detect_mention(user_message, room.get("characters", []))
        room_title = room.get("room_title", "")

        if self._mentions_everyone(user_message):
            return self._plan_for_everyone(room, user_message)

        if self._is_concept_question(user_message):
            return OrchestrationPlan(
                intent="explain_concept",
                target_character=MODERATOR_NAME,
                needs_retrieval=True,
                retrieval_queries=[room_title, user_message],
                speaker_sequence=[
                    SpeakerStep(
                        MODERATOR_NAME,
                        "暂停群聊，用不超过120字解释学生卡住的概念，再用一句话提示这个概念背后的人性或处世问题，"
                        "然后把话题带回当前聊天室。",
                    )
                ],
                max_auto_messages=1,
            )

        if target:
            return self._plan_for_target(room, user_message, target, recent_messages)

        if not recent_messages:
            if room.get("room_type") == "cross_time":
                return OrchestrationPlan(
                    intent="opening",
                    target_character=MODERATOR_NAME,
                    needs_retrieval=True,
                    retrieval_queries=room.get("source_pack_query", [room_title]),
                    speaker_sequence=[
                        SpeakerStep(
                            MODERATOR_NAME,
                            "为跨时空聊天室开场：先说明这是跨时空假想讨论，交代核心问题和比较维度，"
                            "提醒学生可以点名某个人物继续追问。只发一条群主消息，不要自动让其他人物接话。",
                        )
                    ],
                    max_auto_messages=1,
                )
            return OrchestrationPlan(
                intent="opening",
                target_character=MODERATOR_NAME,
                needs_retrieval=True,
                retrieval_queries=room.get("source_pack_query", [room_title]),
                speaker_sequence=[
                    SpeakerStep(
                        MODERATOR_NAME,
                        "为聊天室开场：先说明今天不只看史实，也看人在权力、责任、利益面前怎样选择；"
                        "再点名一个最有冲突感的人物先发言。",
                    ),
                    *self._default_opening_targets(room),
                ],
                max_auto_messages=4,
            )

        plan = OrchestrationPlan(
            intent="general_question",
            target_character=MODERATOR_NAME,
            needs_retrieval=True,
            retrieval_queries=[room_title, user_message],
            speaker_sequence=[
                SpeakerStep(
                    MODERATOR_NAME,
                    "承接学生没有点名的发言，只发一条群主消息：先接住学生情绪或问题，拉回当前史实，"
                    "再点出一个为人处世的观察（如责任、边界、信任、代价、克制、选择），最后给出下一步可@的人物建议。"
                    "不要说教，不要长篇总结，不要在同一轮让其他人物自动发言。",
                )
            ],
            max_auto_messages=1,
        )
        return self._maybe_append_followup_speaker(room, user_message, recent_messages, plan)

    def _plan_for_target(
        self,
        room: dict[str, Any],
        user_message: str,
        target: str,
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> OrchestrationPlan:
        room_title = room.get("room_title", "")
        plan = OrchestrationPlan(
            intent="ask_character",
            target_character=target,
            needs_retrieval=True,
            retrieval_queries=[room_title, target, user_message],
            speaker_sequence=[
                SpeakerStep(
                    target,
                    "你就是被点名人物，必须用第一人称直接回应学生；不要@自己、不要称呼自己、不要让自己出来说。"
                    "如果是临时加入，先用一句话说明只围绕当前主题发言。",
                )
            ],
            max_auto_messages=1,
        )
        return self._maybe_append_followup_speaker(room, user_message, recent_messages or [], plan)

    def _plan_for_everyone(self, room: dict[str, Any], user_message: str) -> OrchestrationPlan:
        room_title = room.get("room_title", "")
        speakers = [
            item.get("name", "")
            for item in room.get("characters", [])
            if item.get("name") and not is_moderator_name(item.get("name"))
        ]
        sequence = [
            SpeakerStep(speaker, "回应学生对全体人物的提问；保持各自立场，发言简短，避免重复前一位。")
            for speaker in speakers
        ]
        return OrchestrationPlan(
            intent="ask_everyone",
            target_character="所有人",
            needs_retrieval=True,
            retrieval_queries=[room_title, user_message],
            speaker_sequence=sequence,
            max_auto_messages=len(sequence),
        )

    def _default_opening_targets(self, room: dict[str, Any]) -> list[SpeakerStep]:
        names = [item.get("name", "") for item in room.get("characters", []) if not is_moderator_name(item.get("name"))]
        if "安禄山" in names:
            return [
                SpeakerStep("安禄山", "先讲自己为什么起兵，发言要像被群主点名。"),
                SpeakerStep("李隆基", "接住安禄山的话，回应信任和失察。"),
                SpeakerStep("杨国忠", "对安禄山的说法提出反驳。"),
            ]
        if "商鞅" in names:
            return [
                SpeakerStep("商鞅", "先说明为什么必须变法。"),
                SpeakerStep("旧贵族代表", "表达既得利益被触动后的不满。"),
            ]
        if room.get("room_type") == "cross_time" and names:
            return [
                SpeakerStep(names[0], "先从自己的时代立场回应核心问题。"),
                SpeakerStep(
                    names[1],
                    "回应前一位人物，指出自己时代的不同条件。",
                )
                if len(names) > 1
                else SpeakerStep(MODERATOR_NAME, "提醒这是跨时空假想讨论。"),
            ]
        return [SpeakerStep(names[0], "围绕主题先开口，保持人物立场。")] if names else []

    def _maybe_append_followup_speaker(
        self,
        room: dict[str, Any],
        user_message: str,
        recent_messages: list[dict[str, Any]],
        plan: OrchestrationPlan,
    ) -> OrchestrationPlan:
        if plan.intent not in {"general_question", "ask_character"}:
            return plan
        if room.get("room_type") == "cross_time" or not plan.speaker_sequence:
            return plan

        primary_speaker = plan.speaker_sequence[0].speaker
        candidate = self._select_followup_candidate(room, user_message, recent_messages, primary_speaker, plan.intent)
        if not candidate:
            return plan

        followup_task = (
            "接住学生问题和群主刚才的话，只补充一个新角度，不要重复，不要重新开场。"
            if plan.intent == "general_question"
            else "针对上一位人物和学生问题，补充对立或纠偏视角；要直接回应，不要重复，不要重新开场。"
        )
        return OrchestrationPlan(
            intent=plan.intent,
            target_character=plan.target_character,
            needs_retrieval=plan.needs_retrieval,
            retrieval_queries=plan.retrieval_queries,
            speaker_sequence=[*plan.speaker_sequence, SpeakerStep(candidate, followup_task)],
            max_auto_messages=min(plan.max_auto_messages + 1, len(plan.speaker_sequence) + 1),
        )

    def _select_followup_candidate(
        self,
        room: dict[str, Any],
        user_message: str,
        recent_messages: list[dict[str, Any]],
        primary_speaker: str,
        intent: str,
    ) -> str | None:
        scores: dict[str, int] = {}
        recent_speakers = [
            str(message.get("sender_name") or "")
            for message in recent_messages[-3:]
            if message.get("sender_name")
        ]
        for character in room.get("characters", []):
            candidate = str(character.get("name") or "")
            if not candidate or is_moderator_name(candidate) or candidate == primary_speaker:
                continue
            score = self._score_followup_candidate(
                candidate, room, user_message, recent_messages, primary_speaker, intent
            )
            if recent_speakers and candidate == recent_speakers[-1]:
                score -= 4
            elif candidate in recent_speakers:
                score -= 2
            scores[candidate] = score

        if not scores:
            return None
        winner = max(scores.items(), key=lambda item: item[1])[0]
        return winner if scores[winner] >= 4 else None

    def _score_followup_candidate(
        self,
        candidate: str,
        room: dict[str, Any],
        user_message: str,
        recent_messages: list[dict[str, Any]],
        primary_speaker: str,
        intent: str,
    ) -> int:
        text = f"{user_message} {self._last_message_content(recent_messages)}"
        score = 0

        if candidate in text:
            score += 5

        if intent == "ask_character":
            dispute_markers = ("逼", "谁", "责任", "错", "怪", "是不是", "还是")
            if candidate in self._conflict_candidates(primary_speaker) and any(
                marker in user_message for marker in dispute_markers
            ):
                score += 3
        else:
            for keyword, boosted_names in self._keyword_followup_preferences(room).items():
                if keyword in text and candidate in boosted_names:
                    score += 3

        if candidate in self._recent_non_primary_speakers(recent_messages, primary_speaker):
            score -= 2
        return score

    @staticmethod
    def _last_message_content(recent_messages: list[dict[str, Any]]) -> str:
        if not recent_messages:
            return ""
        return str(recent_messages[-1].get("content") or "")

    @staticmethod
    def _recent_non_primary_speakers(
        recent_messages: list[dict[str, Any]], primary_speaker: str
    ) -> set[str]:
        return {
            str(message.get("sender_name") or "")
            for message in recent_messages[-2:]
            if message.get("sender_name") and message.get("sender_name") != primary_speaker
        }

    @staticmethod
    def _conflict_candidates(primary_speaker: str) -> list[str]:
        pairs = {
            "安禄山": ["杨国忠", "李隆基"],
            "杨国忠": ["安禄山", "李隆基"],
            "商鞅": ["旧贵族代表", "秦国农民代表"],
            "王安石": ["保守派官僚代表"],
        }
        return pairs.get(primary_speaker, [])

    @staticmethod
    def _keyword_followup_preferences(room: dict[str, Any]) -> dict[str, set[str]]:
        available_names = {str(item.get("name") or "") for item in room.get("characters", [])}

        def present(*names: str) -> set[str]:
            return {name for name in names if name in available_names}

        return {
            "百姓": present("边镇士兵代表", "秦国农民代表", "巴黎市民代表"),
            "苦": present("边镇士兵代表", "秦国农民代表", "巴黎市民代表"),
            "流离": present("边镇士兵代表", "巴黎市民代表"),
            "兵权": present("安禄山", "李隆基", "边镇士兵代表", "郭子仪"),
            "起兵": present("安禄山", "李隆基", "边镇士兵代表"),
            "皇帝": present("李隆基", "秦孝公"),
            "信任": present("李隆基", "秦孝公"),
            "责任": present("李隆基", "秦孝公", "张居正"),
            "改革": present("商鞅", "旧贵族代表", "王安石", "保守派官僚代表"),
            "变法": present("商鞅", "旧贵族代表", "秦国农民代表"),
            "贵族": present("旧贵族代表"),
        }

    @staticmethod
    def _detect_mention(message: str, characters: list[dict[str, Any]]) -> str | None:
        mentions = extract_mentions(message)
        names = {item.get("name") for item in characters}
        for name in mentions:
            if name in names:
                return name
        return None

    @staticmethod
    def _mentions_everyone(message: str) -> bool:
        return any(name in extract_mentions(message) for name in ("所有人", "大家", "全体"))

    @staticmethod
    def _is_concept_question(message: str) -> bool:
        return any(marker in message for marker in ("是什么意思", "什么是", "等一下", "不懂", "解释一下"))
