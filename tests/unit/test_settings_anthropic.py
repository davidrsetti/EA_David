"""Unit tests for config/settings.py — AnthropicSettings dataclass."""
import os
import pytest


def test_enabled_false_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from nexus.config.settings import AnthropicSettings
    s = AnthropicSettings()
    assert s.enabled is False


def test_enabled_true_when_api_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    from nexus.config.settings import AnthropicSettings
    s = AnthropicSettings()
    assert s.enabled is True


def test_default_answer_model():
    from nexus.config.settings import AnthropicSettings
    s = AnthropicSettings()
    assert "claude" in s.answer_model.lower()


def test_default_agent_model():
    from nexus.config.settings import AnthropicSettings
    s = AnthropicSettings()
    assert "claude" in s.agent_model.lower()


def test_default_max_tokens_positive():
    from nexus.config.settings import AnthropicSettings
    s = AnthropicSettings()
    assert s.max_tokens > 0


def test_enable_cache_default_true():
    from nexus.config.settings import AnthropicSettings
    s = AnthropicSettings()
    assert s.enable_cache is True


def test_enable_cache_respects_env(monkeypatch):
    monkeypatch.setenv("CLAUDE_CACHE", "false")
    from nexus.config.settings import AnthropicSettings
    s = AnthropicSettings()
    assert s.enable_cache is False


def test_settings_singleton_has_anthropic_field():
    from nexus.config.settings import settings
    assert hasattr(settings, "anthropic")
    assert hasattr(settings.anthropic, "enabled")
