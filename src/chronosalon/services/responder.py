from __future__ import annotations

import json
import re
from typing import Any

from chronosalon.catalog import MODERATOR_NAME, is_moderator_name
from chronosalon.models import Message
from chronosalon.services.llm_client import OpenAICompatibleModelClient


class LocalRoleplayResponder:
    """Deterministic offline responder used for MVP tests and demos.

    The real LLM client can later replace this class behind the same interface.
    """

    def respond(
        self,
        speaker: str,
        task: str,
        room: dict[str, Any],
        user_message: str = "",
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> Message:
        content = self._content_for(speaker, task, room, user_message, recent_messages or [])
        sender_type = "moderator" if is_moderator_name(speaker) else "character"
        sender_name = MODERATOR_NAME if sender_type == "moderator" else speaker
        labels = ["群聊发言"]
        if sender_type == "moderator":
            labels.append("学习引导")
        elif speaker.endswith("代表"):
            labels.extend(["群体立场模拟", "基于史实推演"])
        else:
            labels.extend(["人物立场", "基于史实推演"])
        return Message(sender_type=sender_type, sender_name=sender_name, content=content, labels=labels)

    def _content_for(
        self,
        speaker: str,
        task: str,
        room: dict[str, Any],
        user_message: str,
        recent_messages: list[dict[str, Any]],
    ) -> str:
        title = room.get("room_title", "")
        if is_moderator_name(speaker):
            return self._host_content(task, title, user_message)
        context_hint = self._context_hint(recent_messages)
        if speaker == "安禄山":
            return (
                "你拿我身形开玩笑可以，但今天要说的是兵权。"
                "我手握三镇，朝廷疑我，杨国忠又步步相逼。"
                "不过把起兵全说成“被逼”，也太便宜我了，我确有野心。"
            )
        if speaker == "李隆基":
            return (
                "朕当年信他，确有失察。古话说“委任既重，疑防反迟”。"
                "翻成现在的话：边镇兵权已经太重，我却醒得太晚。"
            )
        if speaker == "杨国忠":
            return (
                "别把锅全扣到我头上。安禄山拥兵自重，朝廷难道不该防？"
                "我也有私心和争斗，但叛乱不是一句“被逼”就能洗干净。"
            )
        if speaker == "商鞅":
            return (
                "治国不能只靠旧情面。所谓“法不阿贵”，现代话就是：规则不能只保护贵族。"
                "奖励军功、重农耕战，是为了让秦国在诸侯竞争里活下来。"
            )
        if speaker == "秦孝公":
            return "秦国若还守旧制，只会被强国挤压。我支持商鞅，不是爱折腾，是国家已经没有宽松的退路。"
        if speaker == "旧贵族代表":
            return "你们说变法是强国，我们看到的是祖上的特权被拿走。按军功授爵，那出身还有什么用？这是群体立场模拟。"
        if speaker == "秦国农民代表":
            return "我们最关心的是地、粮和赋役。若耕战真能换来奖励，日子也许有奔头；但法令严，也会让人害怕。"
        if speaker == "王安石":
            return "我不反对强力改革，但北宋的问题不只是贵族阻力，还有官僚执行、财政压力和社会承受力。"
        if speaker == "张居正":
            return "改革说到底要落到执行。考成法盯的是官员办不办事，一条鞭法盯的是财政能不能理清。"
        if speaker == "康有为":
            return "我所处的是亡国危机逼近的晚清。维新不是慢慢修补，而是想抢时间，可阻力也因此更猛。"
        if speaker == "保守派官僚代表":
            return "别只说我们守旧。制度一动，官位、财源、秩序都要重排，谁来承担失控的后果？这是群体立场模拟。"
        if speaker == "边镇士兵代表":
            return (
                f"{context_hint}"
                "我们跟着节度使吃粮打仗，离长安很远。朝廷的命令是一回事，将军能不能发饷、带我们活下去又是另一回事。"
            )
        if speaker == "杜甫":
            return (
                f"{context_hint}"
                "我先临时入群，只说安史之乱里的见闻。若从百姓眼里看，战乱不是地图上的箭头，而是流离、饥寒和家国破碎。"
            )
        if speaker == "郭子仪":
            return "我从平叛将领的角度说一句：乱起之后，最难的是重新组织军队和恢复朝廷信用。兵权失衡，收拾起来极难。"
        if speaker == "秦始皇":
            return "若在跨时空讨论里，我会先问：中央能否真正控制地方军政？但若这是安史之乱现场，我不该直接入场。"
        if speaker == "汉武帝":
            return "从大一统治理看，边疆与财政、军权与中央控制必须一起看。只谈某个将领忠不忠，容易漏掉制度问题。"
        if speaker == "拿破仑":
            return "I know power follows armies. 翻成中文：军队会改变权力结构。可历史现场不同，我只能在跨时空比较里发言。"
        return f"{context_hint}我先接一句：这个问题要放回“{title}”的处境里看，不能只用后来的结论倒推。"

    @staticmethod
    def _context_hint(recent_messages: list[dict[str, Any]]) -> str:
        if not recent_messages:
            return ""
        last = recent_messages[-1]
        sender = last.get("sender_name") or last.get("sender") or "前面"
        content = str(last.get("content") or "").strip()
        if not content:
            return ""
        return f"接着{sender}刚才的话说，"

    @staticmethod
    def _host_content(task: str, title: str, user_message: str = "") -> str:
        if "开场" in task:
            if "安史之乱" in title:
                return "安史之乱群聊开张。先不急着背结论，也看人在权力和责任面前怎么选择。@安禄山 你先讲讲，为何从边镇大将走到起兵？"
            if "商鞅" in title:
                return "商鞅变法聊天室开张。今天不先背条目，先看谁得利、谁受损，也看改革者怎样面对阻力。@商鞅 你先说，为什么非变不可？"
            return f"{title}聊天室开张。先听当事人说，也看人在局势里怎样做选择。"
        if "解释" in task:
            return "先暂停一下。这个概念可以理解成一把钥匙：看它掌握了什么权力、谁受益谁受损。处世上也一样，权力越大，边界越要清楚。继续聊。"
        if "承接" in task:
            if any(word in user_message for word in ("百姓", "苦", "可怜", "惨", "流离")):
                return "这句我先接住：你看到的是战乱最后压到普通人身上的痛。学历史也要看决策的代价：掌权者一念失衡，百姓先付账。下一步可以听边镇士兵代表说说战乱压到基层时是什么感觉。"
            if any(word in user_message for word in ("信任", "相信", "用人", "责任", "皇帝")):
                return "这句可以往“信任和边界”上看：信任不是放手不管，责任也不能全推给别人。下一步可以@李隆基追问朝廷为什么没守住制衡。"
            if any(word in user_message for word in ("野心", "权力", "兵权", "失控")):
                return "这句抓到权力失控的线索了。做人处世也是这样：能力越大，越要受约束；野心一旦压过责任，身边人都会被卷进去。可以@安禄山继续追问。"
            return "这句我先接住：我们别只看谁赢谁输，还要看选择背后的责任、边界和代价。下一步可以@一个人物追问他的处境。"
        return "这轮先抓住关键词：权力、利益、制度风险。人物可以互相甩锅，但我们看历史时要把个人选择和结构原因一起看。"


def run_speaking_plan(
    room: dict[str, Any],
    plan: Any,
    user_message: str = "",
    recent_messages: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    responder = LocalRoleplayResponder()
    messages: list[dict[str, Any]] = []
    rolling_context = list(recent_messages or [])
    for step in plan.speaker_sequence[: plan.max_auto_messages]:
        message = responder.respond(step.speaker, step.task, room, user_message, rolling_context).to_dict()
        messages.append(message)
        rolling_context.append(message)
    return messages


class HybridRoleplayResponder:
    """Try an LLM role response first, then fall back to LocalRoleplayResponder."""

    def __init__(self, model_client: OpenAICompatibleModelClient | None = None) -> None:
        self.model_client = model_client
        self.local = LocalRoleplayResponder()

    def respond(
        self,
        speaker: str,
        task: str,
        room: dict[str, Any],
        user_message: str = "",
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> Message:
        content = self._llm_content(speaker, task, room, user_message, recent_messages or [])
        if not content or self._looks_misaligned(speaker, content):
            return self.local.respond(speaker, task, room, user_message, recent_messages)
        content = self._strip_role_prefix(speaker, content)

        sender_type = "moderator" if is_moderator_name(speaker) else "character"
        sender_name = MODERATOR_NAME if sender_type == "moderator" else speaker
        labels = ["大模型生成", "学习引导"] if sender_type == "moderator" else ["大模型生成", "人物立场", "基于史实推演"]
        return Message(sender_type=sender_type, sender_name=sender_name, content=content, labels=labels)

    def _llm_content(
        self,
        speaker: str,
        task: str,
        room: dict[str, Any],
        user_message: str,
        recent_messages: list[dict[str, Any]],
    ) -> str | None:
        if not self.model_client:
            return None
        role = "moderator" if is_moderator_name(speaker) else "character_responder"
        if not self.model_client.is_available(role):
            return None
        system_prompt = (
            "你是 ChronoSalon 的历史群聊生成器。回答必须像群聊发言，不要像课堂讲义。"
            "古文或外文必须立刻翻译成现代简体中文。不得编造史料原文。"
            "群主要短促、会点名、会控场，像群聊主持人，不像讲课老师；人物要有立场和时代语气。"
            "群主还要做史实守门员和人性观察者：适时从责任、边界、信任、代价、克制、选择等角度点一下为人处世，"
            "但必须依附具体历史情境，不准空泛鸡汤，不准长篇说教。"
            "当 speaker 不是“群主”时，你必须扮演 speaker 本人，用第一人称发言；"
            "禁止@自己，禁止说“你来评价/你来说说”，禁止把发言权转交给自己或其他主持人。"
        )
        speaker_profile = self._speaker_profile(speaker, room)
        user_prompt = json.dumps(
            {
                "speaker": speaker,
                "speaker_profile": speaker_profile,
                "task": task,
                "student_message": user_message,
                "recent_messages": self._compact_recent_messages(recent_messages),
                "room": room,
                "output": (
                    f"只输出“{speaker}”本人在群聊里说的一条消息，180字以内。"
                    "不要写角色名，不要写旁白，不要@自己。"
                    "如果 speaker 是群主，控制在60到120字，最多提出一个下一步建议。"
                ),
            },
            ensure_ascii=False,
        )
        return self.model_client.complete(role, system_prompt, user_prompt)

    @staticmethod
    def _compact_recent_messages(recent_messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        compacted = []
        for message in recent_messages[-6:]:
            compacted.append(
                {
                    "sender_name": str(message.get("sender_name", "")),
                    "sender_type": str(message.get("sender_type", "")),
                    "content": str(message.get("content", ""))[:220],
                }
            )
        return compacted

    @staticmethod
    def _speaker_profile(speaker: str, room: dict[str, Any]) -> dict[str, Any]:
        for character in room.get("characters", []):
            if character.get("name") == speaker:
                return character
        return {}

    @staticmethod
    def _looks_misaligned(speaker: str, content: str) -> bool:
        if is_moderator_name(speaker):
            return False
        normalized = content.strip()
        if not normalized:
            return True
        if f"@{speaker}" in normalized:
            return True
        escaped = re.escape(speaker)
        third_person_patterns = [
            rf"{escaped}\s*(你|您)",
            rf"请\s*{escaped}",
            rf"让\s*{escaped}",
            rf"{escaped}\s*(来|出来|说说|评价|回答|怎么看)",
        ]
        return any(re.search(pattern, normalized) for pattern in third_person_patterns)

    @staticmethod
    def _strip_role_prefix(speaker: str, content: str) -> str:
        return re.sub(rf"^\s*{re.escape(speaker)}\s*[：:]\s*", "", content.strip(), count=1)


def run_hybrid_speaking_plan(
    room: dict[str, Any],
    plan: Any,
    user_message: str = "",
    model_client: OpenAICompatibleModelClient | None = None,
    recent_messages: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    responder = HybridRoleplayResponder(model_client)
    messages: list[dict[str, Any]] = []
    rolling_context = list(recent_messages or [])
    for step in plan.speaker_sequence[: plan.max_auto_messages]:
        message = responder.respond(step.speaker, step.task, room, user_message, rolling_context).to_dict()
        messages.append(message)
        rolling_context.append(message)
    return messages
