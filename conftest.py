"""Repo-wide test configuration.

Tests must be deterministic and offline: force the model gateway into replay
mode and ads writes into dry-run BEFORE any service module is imported, so no
test ever spends provider quota or touches a live ad platform.
"""

import os

os.environ["HELM_LLM_PROVIDER"] = "replay"
os.environ["DEFAULT_LLM_PROVIDER"] = "replay"
os.environ["HELM_ADS_DRY_RUN"] = "true"
# Blank the provider keys (not pop): keys.py runs load_dotenv(), which fills
# ABSENT vars from .env but never overrides existing ones — an empty string
# both survives dotenv and fails the has_*_api_key() checks.
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""

import pytest
from modules.ads.byod_importer import clear_active_byod_snapshot


@pytest.fixture(autouse=True)
def reset_test_state():
    """Ensure clean isolated state for each test run."""
    clear_active_byod_snapshot()
    yield
    clear_active_byod_snapshot()

