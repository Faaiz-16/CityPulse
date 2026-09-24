"""The documented configuration must match the real settings."""

from pathlib import Path

from app.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def test_every_env_example_variable_is_a_real_setting():
    fields = {f"CITYPULSE_{name.upper()}" for name in Settings.model_fields} | {"ANTHROPIC_API_KEY"}
    names = [line.split("=", 1)[0].strip() for line in ENV_EXAMPLE.read_text().splitlines()
             if line.strip() and not line.startswith("#")]
    assert names, "no variables found in .env.example"
    unknown = [n for n in names if n not in fields]
    assert unknown == [], f".env.example documents settings that don't exist: {unknown}"


def test_env_example_contains_no_secret_values():
    for line in ENV_EXAMPLE.read_text().splitlines():
        if line.startswith("ANTHROPIC_API_KEY"):
            assert line.strip() == "ANTHROPIC_API_KEY="
