"""Tests for the settings store module."""

import tempfile
import os
from unittest.mock import MagicMock, patch

import pytest

from storage.database import Database
from api.explain_models import LLMProviderEnum, LiteracyLevelEnum, SettingsUpdate
from api import settings_store


@pytest.fixture
def mock_db():
    """Create an isolated Database using a temp file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        yield Database(db_path=path)
    finally:
        os.unlink(path)


@pytest.fixture
def mock_keychain():
    """Create a mock keychain."""
    kc = MagicMock()
    kc.get_claude_key.return_value = None
    kc.get_openai_key.return_value = None
    return kc


class TestGetSettings:
    def test_defaults_when_empty(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            s = settings_store.get_settings()
            assert s.llm_provider == LLMProviderEnum.CLAUDE
            assert s.literacy_level == LiteracyLevelEnum.GRADE_8
            assert s.specialty is None
            assert s.practice_name is None
            assert s.claude_model is None
            assert s.openai_model is None

    def test_reads_stored_values(self, mock_db, mock_keychain):
        mock_db.set_setting("llm_provider", "openai")
        mock_db.set_setting("literacy_level", "grade_8")
        mock_db.set_setting("specialty", "Cardiology")
        mock_db.set_setting("practice_name", "Heart Clinic")
        mock_db.set_setting("claude_model", "claude-sonnet-4-20250514")

        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            s = settings_store.get_settings()
            assert s.llm_provider == LLMProviderEnum.OPENAI
            assert s.literacy_level == LiteracyLevelEnum.GRADE_8
            assert s.specialty == "Cardiology"
            assert s.practice_name == "Heart Clinic"
            assert s.claude_model == "claude-sonnet-4-20250514"


class TestUpdateSettings:
    def test_updates_db_keys(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            update = SettingsUpdate(
                llm_provider=LLMProviderEnum.OPENAI,
                specialty="Pulmonology",
                practice_name="Lung Center",
            )
            result = settings_store.update_settings(update)
            assert result.llm_provider == LLMProviderEnum.OPENAI
            assert result.specialty == "Pulmonology"
            assert result.practice_name == "Lung Center"

    def test_clear_to_null(self, mock_db, mock_keychain):
        mock_db.set_setting("specialty", "Cardiology")
        mock_db.set_setting("practice_name", "Heart Clinic")

        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            # Explicitly set to None to clear
            update = SettingsUpdate(specialty=None, practice_name=None)
            result = settings_store.update_settings(update)
            assert result.specialty is None
            assert result.practice_name is None

    def test_api_key_goes_to_keychain(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            update = SettingsUpdate(claude_api_key="sk-ant-test123")
            settings_store.update_settings(update)
            mock_keychain.set_claude_key.assert_called_once_with("sk-ant-test123")

    def test_empty_update_changes_nothing(self, mock_db, mock_keychain):
        mock_db.set_setting("llm_provider", "openai")
        mock_db.set_setting("specialty", "Cardiology")

        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            update = SettingsUpdate()
            result = settings_store.update_settings(update)
            assert result.llm_provider == LLMProviderEnum.OPENAI
            assert result.specialty == "Cardiology"

    def test_partial_update_preserves_other_fields(self, mock_db, mock_keychain):
        mock_db.set_setting("llm_provider", "claude")
        mock_db.set_setting("specialty", "Cardiology")

        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            update = SettingsUpdate(literacy_level=LiteracyLevelEnum.CLINICAL)
            result = settings_store.update_settings(update)
            assert result.literacy_level == LiteracyLevelEnum.CLINICAL
            # Untouched fields preserved
            assert result.specialty == "Cardiology"
            assert result.llm_provider == LLMProviderEnum.CLAUDE


class TestBooleanSettings:
    def test_boolean_settings_default_true(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            s = settings_store.get_settings()
            assert s.include_key_findings is True
            assert s.include_measurements is True

    def test_boolean_settings_persist_false(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            update = SettingsUpdate(include_key_findings=False, include_measurements=False)
            result = settings_store.update_settings(update)
            assert result.include_key_findings is False
            assert result.include_measurements is False

            # Verify persistence
            s = settings_store.get_settings()
            assert s.include_key_findings is False
            assert s.include_measurements is False


class TestPreferenceSettings:
    def test_tone_preference_default(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            s = settings_store.get_settings()
            assert s.tone_preference == 3
            assert s.detail_preference == 3

    def test_tone_preference_persist(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            update = SettingsUpdate(tone_preference=5, detail_preference=1)
            result = settings_store.update_settings(update)
            assert result.tone_preference == 5
            assert result.detail_preference == 1

            # Verify persistence
            s = settings_store.get_settings()
            assert s.tone_preference == 5
            assert s.detail_preference == 1

    def test_partial_update_preserves_preferences(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            settings_store.update_settings(SettingsUpdate(tone_preference=4))
            result = settings_store.update_settings(SettingsUpdate(detail_preference=2))
            assert result.tone_preference == 4
            assert result.detail_preference == 2


class TestQuickReasonsSettings:
    def test_quick_reasons_default_empty(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            s = settings_store.get_settings()
            assert s.quick_reasons == []

    def test_quick_reasons_persist(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            reasons = ["Chest pain", "Shortness of breath", "Follow-up"]
            update = SettingsUpdate(quick_reasons=reasons)
            result = settings_store.update_settings(update)
            assert result.quick_reasons == reasons

            # Verify persistence
            s = settings_store.get_settings()
            assert s.quick_reasons == reasons

    def test_quick_reasons_clear_to_empty(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            settings_store.update_settings(SettingsUpdate(quick_reasons=["Chest pain"]))
            result = settings_store.update_settings(SettingsUpdate(quick_reasons=[]))
            assert result.quick_reasons == []

    def test_partial_update_preserves_quick_reasons(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            settings_store.update_settings(SettingsUpdate(quick_reasons=["Chest pain"]))
            result = settings_store.update_settings(SettingsUpdate(tone_preference=5))
            assert result.quick_reasons == ["Chest pain"]
            assert result.tone_preference == 5


class TestNextStepsOptionsSettings:
    def test_next_steps_options_default(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            s = settings_store.get_settings()
            assert s.next_steps_options == [
                "Will follow this over time",
                "We will contact you to discuss next steps",
            ]

    def test_next_steps_options_persist(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            options = ["Schedule follow-up", "Repeat in 6 months"]
            update = SettingsUpdate(next_steps_options=options)
            result = settings_store.update_settings(update)
            assert result.next_steps_options == options

            s = settings_store.get_settings()
            assert s.next_steps_options == options

    def test_next_steps_options_clear_to_empty(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            settings_store.update_settings(SettingsUpdate(next_steps_options=["Some step"]))
            result = settings_store.update_settings(SettingsUpdate(next_steps_options=[]))
            assert result.next_steps_options == []

    def test_partial_update_preserves_next_steps(self, mock_db, mock_keychain):
        with patch.object(settings_store, "get_db", return_value=mock_db), \
             patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            settings_store.update_settings(SettingsUpdate(next_steps_options=["Custom step"]))
            result = settings_store.update_settings(SettingsUpdate(tone_preference=2))
            assert result.next_steps_options == ["Custom step"]
            assert result.tone_preference == 2


class TestGetApiKeyForProvider:
    def test_claude_key(self, mock_keychain):
        mock_keychain.get_claude_key.return_value = "sk-claude"
        with patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            assert settings_store.get_api_key_for_provider("claude") == "sk-claude"

    def test_openai_key(self, mock_keychain):
        mock_keychain.get_openai_key.return_value = "sk-openai"
        with patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            assert settings_store.get_api_key_for_provider("openai") == "sk-openai"

    def test_unknown_provider(self, mock_keychain):
        with patch.object(settings_store, "get_keychain", return_value=mock_keychain):
            assert settings_store.get_api_key_for_provider("unknown") is None
