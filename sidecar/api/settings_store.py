"""
In-memory settings store (Phase 4).

Simple module-level singleton. Phase 6 will replace with SQLite + OS keychain.
"""

from __future__ import annotations

from api.explain_models import AppSettings, SettingsUpdate


_settings = AppSettings()


def get_settings() -> AppSettings:
    """Return current settings (copy)."""
    return _settings.model_copy()


def update_settings(update: SettingsUpdate) -> AppSettings:
    """Apply partial update and return new settings."""
    global _settings
    update_data = update.model_dump(exclude_none=True)
    current_data = _settings.model_dump()
    current_data.update(update_data)
    _settings = AppSettings(**current_data)
    return _settings.model_copy()


def get_api_key_for_provider(provider: str) -> str | None:
    """Get the API key for the given provider."""
    if provider == "claude":
        return _settings.claude_api_key
    elif provider == "openai":
        return _settings.openai_api_key
    return None
