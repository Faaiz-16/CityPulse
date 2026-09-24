"""Shared test setup: an isolated SQLite file and no background loop."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="citypulse-tests-"))
os.environ["CITYPULSE_DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["CITYPULSE_RUN_BACKGROUND_LOOP"] = "false"
os.environ["CITYPULSE_LIVE_APIS"] = "false"
os.environ["ANTHROPIC_API_KEY"] = ""

import pytest  # noqa: E402

from app.config import Settings  # noqa: E402
from app.services.pipeline import CityPulse  # noqa: E402

# 15:00 in Asia/Kolkata — mid-afternoon, away from rush-hour peaks.
T0 = datetime(2026, 9, 24, 9, 30, tzinfo=UTC)


@pytest.fixture
def settings() -> Settings:
    return Settings(run_background_loop=False, live_apis=False)


@pytest.fixture
def pipeline(settings) -> CityPulse:
    p = CityPulse(settings)
    p.startup(T0)
    return p
