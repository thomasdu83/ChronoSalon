from pathlib import Path

from chronosalon.services.llm_client import OpenAICompatibleModelClient


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / ".test_tmp"


def test_llm_client_reports_unavailable_without_key():
    TMP.mkdir(exist_ok=True)
    config = TMP / "missing_key_model_config.yaml"
    config.write_text(
        """
models:
  character_responder:
    provider: "test"
    model_name: "test-model"
    api_key_env: "MISSING_CHRONOSALON_TEST_KEY"
    base_url: "https://example.invalid/v1"
    temperature: 0.5
    max_tokens: 100
""",
        encoding="utf-8",
    )

    client = OpenAICompatibleModelClient(config)

    assert not client.is_available("character_responder")
    assert client.complete("character_responder", "system", "user") is None


def test_llm_client_reads_dotenv_key_without_exposing_value():
    TMP.mkdir(exist_ok=True)
    config = TMP / "dotenv_model_config.yaml"
    env = TMP / ".env.test"
    config.write_text(
        """
models:
  moderator:
    provider: "test"
    model_name: "test-model"
    api_key_env: "CHRONOSALON_TEST_KEY"
    base_url: "https://example.invalid/v1"
    temperature: 0.5
    max_tokens: 100
""",
        encoding="utf-8",
    )
    env.write_text("CHRONOSALON_TEST_KEY=secret-value\n", encoding="utf-8")

    client = OpenAICompatibleModelClient(config, env)

    assert client.is_available("moderator")
