"""API key custody and resolution."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded from root
root_dir = Path(__file__).resolve().parent.parent.parent.parent
env_path = root_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()


def get_anthropic_api_key() -> str | None:
    """Retrieve Anthropic API key from backend environment."""
    return os.environ.get("ANTHROPIC_API_KEY")


def has_anthropic_api_key() -> bool:
    """Check if Anthropic API key is configured."""
    key = get_anthropic_api_key()
    return bool(key and len(key.strip()) > 0)


def get_gemini_api_key() -> str | None:
    """Retrieve Google Gemini API key from backend environment."""
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def has_gemini_api_key() -> bool:
    """Check if Gemini API key is configured."""
    key = get_gemini_api_key()
    return bool(key and len(key.strip()) > 0)


DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"


def get_active_provider() -> str:
    """Get active LLM provider ('gemini' | 'anthropic' | 'replay')."""
    return (
        os.environ.get("HELM_LLM_PROVIDER") or os.environ.get("DEFAULT_LLM_PROVIDER") or "gemini"
    ).lower()


def get_model_for_provider(provider: str, fast: bool = False) -> str:
    """Get configured model name for the given provider."""
    provider = provider.lower()
    if provider == "gemini":
        if fast:
            return os.environ.get("GEMINI_FAST_MODEL", DEFAULT_GEMINI_MODEL)
        return os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    elif provider == "anthropic":
        return os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    return "deterministic-replay-v1"

