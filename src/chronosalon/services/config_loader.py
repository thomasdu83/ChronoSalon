from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelRoleConfig:
    role: str
    provider: str
    model_name: str
    api_key_env: str
    base_url: str
    temperature: float
    max_tokens: int


class ModelConfigLoader:
    """Loads model role settings.

    PyYAML is used when available. A small fallback parser handles the simple
    template shape used by this project so tests can run without dependencies.
    """

    def load(self, path: str | Path) -> dict[str, ModelRoleConfig]:
        text = Path(path).read_text(encoding="utf-8")
        data = self._load_yaml(text)
        models = data.get("models", {})
        return {
            role: ModelRoleConfig(
                role=role,
                provider=str(config.get("provider", "")),
                model_name=str(config.get("model_name", "")),
                api_key_env=str(config.get("api_key_env", "")),
                base_url=str(config.get("base_url", "")),
                temperature=float(config.get("temperature", 0.4)),
                max_tokens=int(config.get("max_tokens", 1000)),
            )
            for role, config in models.items()
        }

    def _load_yaml(self, text: str) -> dict[str, Any]:
        try:
            import yaml  # type: ignore

            return yaml.safe_load(text) or {}
        except Exception:
            return self._fallback_parse(text)

    @staticmethod
    def _fallback_parse(text: str) -> dict[str, Any]:
        result: dict[str, Any] = {"models": {}}
        current_role: str | None = None
        in_models = False
        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            if line == "models:":
                in_models = True
                continue
            if not in_models:
                continue
            if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":"):
                current_role = line.strip()[:-1]
                result["models"][current_role] = {}
                continue
            if current_role and line.startswith("    ") and ":" in line:
                key, value = line.strip().split(":", 1)
                value = value.strip().strip('"').strip("'")
                if value.replace(".", "", 1).isdigit():
                    parsed: Any = float(value) if "." in value else int(value)
                else:
                    parsed = value
                result["models"][current_role][key] = parsed
        return result

