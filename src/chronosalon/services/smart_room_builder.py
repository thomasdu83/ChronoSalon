from __future__ import annotations

import logging

from chronosalon.catalog import moderator_character
from chronosalon.models import RoomDraft

logger = logging.getLogger(__name__)


class SmartRoomBuilder:
    """Build deterministic fallback rooms for recognizable but uncatalogued topics."""

    era_rules: tuple[tuple[str, tuple[str, ...], str], ...] = (
        (
            "晚清",
            ("戊戌", "甲午", "庚子", "晚清", "清末", "洋务"),
            "晚清，主题相关历史时段前后",
        ),
        ("晚清", ("鸦片", "道光"), "晚清，道光年间前后"),
        ("晚清", ("辛亥",), "晚清至民初，主题相关历史时段前后"),
        ("民初", ("五四", "新文化", "北洋", "民初", "巴黎和会"), "民初，1910年代前后"),
        (
            "唐朝",
            ("唐朝", "唐代", "安史", "开元", "贞观"),
            "唐朝，主题相关历史时段前后",
        ),
        ("战国", ("战国", "秦国", "商鞅"), "战国时期，主题相关历史时段前后"),
        ("北宋", ("北宋", "宋朝", "王安石"), "北宋，主题相关历史时段前后"),
        ("明朝", ("明朝", "张居正", "万历"), "明朝，主题相关历史时段前后"),
    )

    def build(self, topic: str) -> RoomDraft | None:
        """Return a minimum viable historical scene draft, or None when topic is too unclear."""
        event_type = self._infer_event_type(topic)
        era = self._infer_era(topic)
        if not event_type or not era:
            logger.info(
                "Smart room builder skipped for topic=%s event_type=%s era=%s",
                topic,
                event_type,
                era,
            )
            return None

        if event_type == "reform":
            return self._build_reform_room(topic, era)
        if event_type == "revolution":
            return self._build_revolution_room(topic, era)
        if event_type == "war":
            return self._build_war_room(topic, era)
        if event_type == "movement":
            return self._build_movement_room(topic, era)
        return None

    def _infer_event_type(self, topic: str) -> str | None:
        if any(keyword in topic for keyword in ("变法", "改革", "新政")):
            return "reform"
        if any(keyword in topic for keyword in ("革命", "起义")):
            return "revolution"
        if any(keyword in topic for keyword in ("战争", "战役", "之战")):
            return "war"
        if "运动" in topic:
            return "movement"
        return None

    def _infer_era(self, topic: str) -> dict[str, str | list[str]] | None:
        for primary_era, keywords, time_range in self.era_rules:
            if any(keyword in topic for keyword in keywords):
                allowed = ["晚清", "民初"] if "辛亥" in topic else [primary_era]
                return {
                    "primary_era": primary_era,
                    "time_range": time_range,
                    "allowed_eras": allowed,
                }
        return None

    def _build_reform_room(
        self, topic: str, era: dict[str, str | list[str]]
    ) -> RoomDraft:
        primary_era = str(era["primary_era"])
        return RoomDraft(
            status="ready",
            room_title=topic,
            room_type="historical_scene",
            topic_boundary=f"围绕“{topic}”的背景、推动力量、阻力、执行过程和历史影响展开历史现场讨论。",
            time_range=str(era["time_range"]),
            learning_goals=[
                "了解改革背景",
                "比较支持者与反对者立场",
                "分析改革为何推进或受阻",
            ],
            characters=[
                moderator_character(),
                self._group_character(
                    primary_era, "改革推动者代表", "主张制度调整和现实改造的推动者"
                ),
                self._group_character(
                    primary_era, "最高决策者代表", "掌握改革生杀予夺权力的最高决策者"
                ),
                self._group_character(
                    primary_era,
                    "保守派官僚代表",
                    "担忧秩序、权力和既得利益受损的反对力量",
                ),
                self._group_character(
                    primary_era,
                    "普通士人代表",
                    "观察改革成本、机会与社会反应的基层士人",
                ),
            ],
            recommended_questions=[
                "@改革推动者代表 你最想改变什么制度？",
                "@保守派官僚代表 你为什么反对这场改革？",
                "@最高决策者代表 你为什么支持、犹豫或放弃？",
            ],
            source_pack_query=[
                topic,
                f"{topic} 背景",
                f"{topic} 阻力",
                f"{topic} 影响",
            ],
            scene_allowed_eras=list(era["allowed_eras"]),
        )

    def _build_revolution_room(
        self, topic: str, era: dict[str, str | list[str]]
    ) -> RoomDraft:
        primary_era = str(era["primary_era"])
        return RoomDraft(
            status="ready",
            room_title=topic,
            room_type="historical_scene",
            topic_boundary=f"围绕“{topic}”的爆发背景、组织力量、政治目标和社会后果展开历史现场讨论。",
            time_range=str(era["time_range"]),
            learning_goals=[
                "理解革命目标",
                "分析旧政权与新力量冲突",
                "观察社会群体的不同期待",
            ],
            characters=[
                moderator_character(),
                self._group_character(
                    primary_era, "革命派代表", "主张推翻旧秩序或推动政权改造的行动者"
                ),
                self._group_character(
                    primary_era, "旧政权代表", "维护既有统治结构和政治合法性的力量"
                ),
                self._group_character(
                    primary_era, "武装力量代表", "决定局势走向的重要军事或治安力量"
                ),
                self._group_character(
                    primary_era, "城市民众代表", "关心社会秩序、生活与政治希望的普通人"
                ),
            ],
            recommended_questions=[
                "@革命派代表 你们为何认定必须改变旧制度？",
                "@旧政权代表 你们最担心失去什么？",
                "@武装力量代表 你们为什么会影响最终结果？",
            ],
            source_pack_query=[
                topic,
                f"{topic} 背景",
                f"{topic} 经过",
                f"{topic} 结果",
            ],
            scene_allowed_eras=list(era["allowed_eras"]),
        )

    def _build_war_room(self, topic: str, era: dict[str, str | list[str]]) -> RoomDraft:
        primary_era = str(era["primary_era"])
        return RoomDraft(
            status="ready",
            room_title=topic,
            room_type="historical_scene",
            topic_boundary=f"围绕“{topic}”的战争起因、决策失误、交战双方与社会影响展开历史现场讨论。",
            time_range=str(era["time_range"]),
            learning_goals=[
                "理解战争起因",
                "比较决策层与前线视角",
                "分析战争带来的制度与社会变化",
            ],
            characters=[
                moderator_character(),
                self._group_character(
                    primary_era, "决策者代表", "负责战争决策与外交取舍的统治层"
                ),
                self._group_character(
                    primary_era, "前线将领代表", "直接面对军事压力与战场局势的将领"
                ),
                self._group_character(
                    primary_era, "对手阵营代表", "站在另一方立场理解利益与目标"
                ),
                self._group_character(
                    primary_era, "战地民众代表", "承受战争成本和秩序变化的普通民众"
                ),
            ],
            recommended_questions=[
                "@决策者代表 这场战争为什么会走到无法回头？",
                "@前线将领代表 你看到的关键问题是什么？",
                "@战地民众代表 战争怎样改变了普通人的生活？",
            ],
            source_pack_query=[
                topic,
                f"{topic} 原因",
                f"{topic} 过程",
                f"{topic} 影响",
            ],
            scene_allowed_eras=list(era["allowed_eras"]),
        )

    def _build_movement_room(
        self, topic: str, era: dict[str, str | list[str]]
    ) -> RoomDraft:
        primary_era = str(era["primary_era"])
        return RoomDraft(
            status="ready",
            room_title=topic,
            room_type="historical_scene",
            topic_boundary=f"围绕“{topic}”的发起背景、参与群体、舆论争论和历史影响展开历史现场讨论。",
            time_range=str(era["time_range"]),
            learning_goals=[
                "理解运动爆发背景",
                "观察不同群体参与逻辑",
                "分析思想与社会影响",
            ],
            characters=[
                moderator_character(),
                self._group_character(
                    primary_era, "发起者代表", "推动议题扩散和行动升级的主要发起群体"
                ),
                self._group_character(
                    primary_era, "官方代表", "负责回应、压制或引导运动的政治力量"
                ),
                self._group_character(
                    primary_era, "知识界代表", "提供思想资源、舆论解释和教育影响的群体"
                ),
                self._group_character(
                    primary_era,
                    "社会群众代表",
                    "在现实生活中感受运动冲击与机会的参与者",
                ),
            ],
            recommended_questions=[
                "@发起者代表 你们为什么要走上街头或公开发声？",
                "@官方代表 你们如何看待这场运动的要求？",
                "@知识界代表 这场运动留下了什么思想影响？",
            ],
            source_pack_query=[
                topic,
                f"{topic} 背景",
                f"{topic} 参与群体",
                f"{topic} 影响",
            ],
            scene_allowed_eras=list(era["allowed_eras"]),
        )

    @staticmethod
    def _group_character(era: str, name: str, role: str) -> dict[str, str]:
        return {
            "id": f"smart_{era}_{name}",
            "name": name,
            "type": "group_character",
            "era": era,
            "identity": f"{era}{name}",
            "role": role,
            "position": role,
            "must_label": "群体立场模拟，不代表某个具体历史人物原话。",
        }
