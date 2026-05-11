from __future__ import annotations

import re
from typing import Any

from chronosalon.catalog import CHARACTERS, find_character_by_name, temporary_character_dict


def extract_mentions(message: str) -> list[str]:
    return [item.strip() for item in re.findall(r"@([^\s，,。.!！?？:：]+)", message) if item.strip()]


def room_character_names(room: dict[str, Any]) -> set[str]:
    return {item.get("name", "") for item in room.get("characters", [])}


def prepare_mentioned_character(room: dict[str, Any], message: str) -> dict[str, Any]:
    """Handle @ mentions before orchestration.

    Returns:
    - room: updated room, possibly with a temporary character appended.
    - target: first mentioned name, if any.
    - added_character: temporary character payload, if one was added.
    - blocked_reason: moderator-facing reason when historical-scene boundaries block the mention.
    """

    mentions = extract_mentions(message)
    if not mentions:
        return {"room": room, "target": None, "added_character": None, "blocked_reason": None}

    targets = [resolve_mention_target(room, mention) for mention in mentions]
    existing_names = room_character_names(room)
    special_targets = {"所有人", "大家", "全体"}

    for mentioned_target in targets:
        if mentioned_target in special_targets or mentioned_target in existing_names:
            continue
        blocked_reason = historical_scene_block_reason(room, mentioned_target)
        if blocked_reason:
            return {"room": room, "target": mentioned_target, "added_character": None, "blocked_reason": blocked_reason}

    target = targets[0]
    if target in {"所有人", "大家", "全体"}:
        return {"room": room, "target": target, "added_character": None, "blocked_reason": None}

    if target in existing_names:
        return {"room": room, "target": target, "added_character": None, "blocked_reason": None}

    added_character = temporary_character_dict(target, room)
    updated_room = dict(room)
    updated_room["characters"] = list(room.get("characters", [])) + [added_character]
    return {"room": updated_room, "target": target, "added_character": added_character, "blocked_reason": None}


def resolve_mention_target(room: dict[str, Any], mention: str) -> str:
    """Normalize mentions that are followed immediately by Chinese text.

    For example, "@杜甫听百姓视角" should still resolve to "杜甫".
    """

    for special in ("所有人", "大家", "全体"):
        if mention == special or mention.startswith(special):
            return special

    candidate_names = sorted(
        {
            *room_character_names(room),
            *(character.name for character in CHARACTERS.values()),
        },
        key=len,
        reverse=True,
    )
    for name in candidate_names:
        if name and (mention == name or mention.startswith(name)):
            return name
    return mention


def historical_scene_block_reason(room: dict[str, Any], target: str) -> str | None:
    if room.get("room_type") != "historical_scene":
        return None

    room_title = room.get("room_title", "当前聊天室")
    forbidden_names = set(room.get("scene_forbidden_names", []))
    if target in forbidden_names:
        return (
            f"先拦一下，@{target} 不属于“{room_title}”这个历史现场，不能进入本群。"
            "如果想让不同时空人物一起讨论，请新建或切换到“跨时空讨论”聊天室。"
        )

    known = find_character_by_name(target)
    allowed_eras = set(room.get("scene_allowed_eras", []))
    if known and allowed_eras and known.era not in allowed_eras:
        return (
            f"先拦一下，@{target} 是{known.era}人物，不在“{room_title}”的现场时空里，不能进入本群。"
            "这个问题适合放到“跨时空讨论”聊天室。"
        )

    if allowed_eras and known is None:
        allowed_text = "、".join(sorted(allowed_eras))
        return (
            f"先拦一下，我还不能确认 @{target} 属于“{room_title}”的现场时空（{allowed_text}），"
            "所以不能直接放进历史现场。"
            "如果想让不同人物跨时代讨论，请新建或切换到“跨时空讨论”聊天室。"
        )

    return None
