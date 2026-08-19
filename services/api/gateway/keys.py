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


def get_active_provider() -> str:
    """Get active LLM provider ('anthropic' | 'gemini' | 'replay').

    Anthropic is the default: HELM runs on Claude unless explicitly told
    otherwise. If the configured provider has no key but Anthropic does, fall
    through to Anthropic rather than silently degrading to replay.
    """
    configured = (
        os.environ.get("HELM_LLM_PROVIDER") or os.environ.get("DEFAULT_LLM_PROVIDER") or "anthropic"
    ).lower()
    if configured == "gemini" and not has_gemini_api_key() and has_anthropic_api_key():
        return "anthropic"
    return configured


def get_model_for_provider(provider: str, fast: bool = False) -> str:
    """Get configured model name for the given provider."""
    provider = provider.lower()
    if provider == "gemini":
        if fast:
            return os.environ.get("GEMINI_FAST_MODEL", "gemini-2.5-flash")
        return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    elif provider == "anthropic":
        # Every task routes to the primary model — HELM's outputs drive real
        # budget decisions, so no task gets a downgraded model.
        return os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
    return "deterministic-replay-v1"

