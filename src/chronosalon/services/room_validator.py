from __future__ import annotations

from chronosalon.catalog import find_character_by_name, is_moderator_name
from chronosalon.models import RoomDraft


class RoomValidator:
    """Enforce minimum viability before a room can be returned as ready."""

    def validate(self, draft: RoomDraft) -> RoomDraft:
        if draft.status != "ready":
            return draft

        errors = self._collect_errors(draft)
        if not errors:
            return draft

        return RoomDraft(
            status="needs_choice",
            room_title=draft.room_title or "选择一个历史主题",
            room_type=None,
            topic_boundary=f"当前主题信息还不足以建成可讨论聊天室：{'；'.join(errors)}",
            options=self._fallback_options(draft.room_title),
        )

    def _collect_errors(self, draft: RoomDraft) -> list[str]:
        errors: list[str] = []
        characters = list(draft.characters)
        non_moderators = [
            item for item in characters if not is_moderator_name(item.get("name"))
        ]
        recommended_questions = [
            item for item in draft.recommended_questions if str(item).strip()
        ]

        if not any(is_moderator_name(item.get("name")) for item in characters):
            errors.append("缺少群主")
        if len(non_moderators) < 3:
            errors.append("历史人物或群体角色不足 3 个")
        if not draft.topic_boundary.strip():
            errors.append("缺少主题边界")
        if len(recommended_questions) < 3:
            errors.append("推荐问题不足 3 个")
        if recommended_questions and not any(
            str(item).strip().startswith("@") for item in recommended_questions
        ):
            errors.append("推荐问题缺少 @人物 引导")

        if draft.room_type == "historical_scene":
            if not draft.time_range.strip():
                errors.append("历史现场缺少时代范围")
            if not draft.scene_allowed_eras:
                errors.append("历史现场缺少允许时代边界")
            conflicting_names = self._conflicting_character_names(
                non_moderators, draft.scene_allowed_eras
            )
            if conflicting_names:
                errors.append(f"人物时代冲突：{'、'.join(conflicting_names)}")
        return errors

    def _conflicting_character_names(
        self, characters: list[dict], allowed_eras: list[str]
    ) -> list[str]:
        if not allowed_eras:
            return []

        conflicts: list[str] = []
        for item in characters:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            canonical = find_character_by_name(name)
            character_era = (
                canonical.era if canonical else str(item.get("era") or "").strip()
            )
            if character_era and not self._era_matches_allowed(
                character_era, allowed_eras
            ):
                conflicts.append(name)
        return conflicts

    @staticmethod
    def _era_matches_allowed(character_era: str, allowed_eras: list[str]) -> bool:
        normalized_era = character_era.strip()
        if not normalized_era:
            return False
        for allowed in allowed_eras:
            normalized_allowed = str(allowed).strip()
            if not normalized_allowed:
                continue
            if normalized_era == normalized_allowed:
                return True
            if (
                normalized_allowed in normalized_era
                or normalized_era in normalized_allowed
            ):
                return True
        return False

    @staticmethod
    def _fallback_options(room_title: str) -> list[str]:
        return [
            room_title,
            f"{room_title} 背景",
            f"{room_title} 关键人物",
            f"{room_title} 为什么失败或成功",
        ]
