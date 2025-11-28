"""Tests for configuration."""

import pytest

from chuk_mcp_time.config import TimeServerConfig, load_config


def test_config_defaults() -> None:
    """Test configuration default values."""
    config = TimeServerConfig()

    assert len(config.ntp_servers) == 7
    assert "time.google.com" in config.ntp_servers
    assert "time.cloudflare.com" in config.ntp_servers
    assert config.ntp_timeout == 2.0
    assert config.max_outlier_deviation_ms == 5000.0
    assert config.min_sources == 3
    assert config.max_disagreement_ms == 250.0
    assert config.fast_mode_server_count == 4


def test_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test configuration from environment variables."""
    monkeypatch.setenv("TIME_SERVER_NTP_TIMEOUT", "5.0")
    monkeypatch.setenv("TIME_SERVER_MIN_SOURCES", "5")
    monkeypatch.setenv("TIME_SERVER_FAST_MODE_SERVER_COUNT", "3")

    config = TimeServerConfig()

    assert config.ntp_timeout == 5.0
    assert config.min_sources == 5
    assert config.fast_mode_server_count == 3


def test_config_validation() -> None:
    """Test configuration validation."""
    from pydantic import ValidationError

    # Valid config
    config = TimeServerConfig(
        ntp_timeout=3.0,
        min_sources=2,
        max_outlier_deviation_ms=1000.0,
    )
    assert config.ntp_timeout == 3.0

    # Invalid values should raise validation error
    with pytest.raises(ValidationError):
        TimeServerConfig(ntp_timeout=0.1)  # Below minimum

    with pytest.raises(ValidationError):
        TimeServerConfig(ntp_timeout=20.0)  # Above maximum

    with pytest.raises(ValidationError):
        TimeServerConfig(min_sources=0)  # Below minimum


def test_load_config() -> None:
    """Test load_config function."""
    config = load_config()
    assert isinstance(config, TimeServerConfig)
    assert len(config.ntp_servers) > 0


def test_get_config() -> None:
    """Test get_config function (singleton pattern)."""
    from chuk_mcp_time.config import get_config

    # First call
    config1 = get_config()
    assert isinstance(config1, TimeServerConfig)

    # Second call should return same instance
    config2 = get_config()
    assert config1 is config2  # Same object reference
