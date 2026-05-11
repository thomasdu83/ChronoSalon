from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from chronosalon.services.config_loader import ModelConfigLoader, ModelRoleConfig
from chronosalon.services.env_loader import load_dotenv_values


class OpenAICompatibleModelClient:
    """Small OpenAI-compatible chat client.

    It is intentionally conservative: missing keys, bad config, network errors,
    provider errors, and malformed responses all return None so callers can use
    deterministic fallback behavior.
    """

    def __init__(self, config_path: str | Path, env_path: str | Path | None = None) -> None:
        self.configs = ModelConfigLoader().load(config_path)
        self.dotenv = load_dotenv_values(env_path) if env_path else {}

    def is_available(self, role: str) -> bool:
        config = self.configs.get(role)
        return bool(config and self._api_key(config))

    def complete(self, role: str, system_prompt: str, user_prompt: str, timeout: float = 25.0) -> str | None:
        config = self.configs.get(role)
        if not config:
            return None
        api_key = self._api_key(config)
        if not api_key:
            return None

        try:
            import httpx

            response = httpx.post(
                self._chat_url(config),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            return payload["choices"][0]["message"]["content"].strip() or None
        except Exception:
            return None

    def _api_key(self, config: ModelRoleConfig) -> str | None:
        return os.environ.get(config.api_key_env) or self.dotenv.get(config.api_key_env)

    @staticmethod
    def _chat_url(config: ModelRoleConfig) -> str:
        base_url = config.base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"

