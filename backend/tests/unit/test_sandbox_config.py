"""
Unit tests for SandboxConfig.

Tests configuration validation and settings management.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestSandboxServerConfig:
    """Test SandboxServerConfig settings."""

    def test_default_server_config(self):
        """Test default server configuration values."""
        from backend.src.sandbox.sandbox_server.config import SandboxServerConfig
        
        config = SandboxServerConfig()
        
        assert config.host == "0.0.0.0"
        assert config.port == 8100
        assert "postgresql" in config.database_url

    def test_custom_server_config(self):
        """Test custom server configuration values."""
        from backend.src.sandbox.sandbox_server.config import SandboxServerConfig
        
        config = SandboxServerConfig(
            host="127.0.0.1",
            port=9000,
            database_url="postgresql://custom:password@localhost/test"
        )
        
        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert "custom" in config.database_url


class TestSandboxConfig:
    """Test SandboxConfig for sandbox management."""

    @pytest.fixture
    def mock_settings(self):
        """Mock the backend.core.conf.settings."""
        with patch("backend.src.sandbox.sandbox_server.config.settings") as mock:
            mock.REDIS_HOST = "localhost"
            mock.REDIS_PORT = 6379
            mock.REDIS_PASSWORD = ""
            mock.REDIS_DATABASE = 0
            mock.E2B_API_KEY = "test_e2b_key"
            mock.E2B_TEMPLATE_ID = "base"
            mock.DAYTONA_API_KEY = "test_daytona_key"
            mock.DAYTONA_SERVER_URL = "https://app.daytona.io/api"
            mock.DAYTONA_TARGET = "us"
            yield mock

    def test_default_provider_type(self, mock_settings):
        """Test default provider type is e2b."""
        with patch("backend.core.conf.settings", mock_settings):
            from backend.src.sandbox.sandbox_server.config import SandboxConfig
            
            config = SandboxConfig()
            assert config.provider_type == "e2b"

    def test_default_timeout_values(self, mock_settings):
        """Test default timeout configuration."""
        with patch("backend.core.conf.settings", mock_settings):
            from backend.src.sandbox.sandbox_server.config import SandboxConfig
            
            config = SandboxConfig()
            
            # Default timeout is 2 hours
            assert config.timeout_seconds == 60 * 60 * 2
            # Pause before timeout is 10 minutes
            assert config.pause_before_timeout_seconds == 60 * 10

    def test_redis_url_construction(self, mock_settings):
        """Test Redis URL is constructed from settings."""
        with patch("backend.core.conf.settings", mock_settings):
            from backend.src.sandbox.sandbox_server.config import SandboxConfig
            
            config = SandboxConfig()
            
            assert "redis://" in config.redis_url
            assert "localhost" in config.redis_url

    def test_redis_url_with_password(self, mock_settings):
        """Test Redis URL includes password when set."""
        mock_settings.REDIS_PASSWORD = "secret"
        
        with patch("backend.core.conf.settings", mock_settings):
            from backend.src.sandbox.sandbox_server.config import SandboxConfig
            
            config = SandboxConfig()
            
            assert ":secret@" in config.redis_url

    def test_e2b_settings(self, mock_settings):
        """Test E2B-specific settings are loaded."""
        with patch("backend.core.conf.settings", mock_settings):
            from backend.src.sandbox.sandbox_server.config import SandboxConfig
            
            config = SandboxConfig()
            
            assert config.e2b_api_key == "test_e2b_key"
            assert config.e2b_template_id == "base"

    def test_get_provider_config_e2b(self, mock_settings):
        """Test get_provider_config returns E2B config."""
        with patch("backend.core.conf.settings", mock_settings):
            from backend.src.sandbox.sandbox_server.config import SandboxConfig
            
            config = SandboxConfig()
            provider_config = config.get_provider_config()
            
            assert "api_key" in provider_config
            assert "template" in provider_config

    def test_get_queue_config_redis(self, mock_settings):
        """Test get_queue_config returns Redis config."""
        with patch("backend.core.conf.settings", mock_settings):
            from backend.src.sandbox.sandbox_server.config import SandboxConfig
            
            config = SandboxConfig()
            queue_config = config.get_queue_config()
            
            assert queue_config is not None
            assert "redis_url" in queue_config
            assert "queue_name" in queue_config

    def test_has_queue_provider_property(self, mock_settings):
        """Test has_queue_provider property."""
        with patch("backend.core.conf.settings", mock_settings):
            from backend.src.sandbox.sandbox_server.config import SandboxConfig
            
            config = SandboxConfig()
            
            assert config.has_queue_provider is True

    def test_sandbox_provider_alias(self, mock_settings):
        """Test sandbox_provider property is alias for provider_type."""
        with patch("backend.core.conf.settings", mock_settings):
            from backend.src.sandbox.sandbox_server.config import SandboxConfig
            
            config = SandboxConfig()
            
            assert config.sandbox_provider == config.provider_type

    def test_resource_limits_defaults(self, mock_settings):
        """Test default resource limits."""
        with patch("backend.core.conf.settings", mock_settings):
            from backend.src.sandbox.sandbox_server.config import SandboxConfig
            
            config = SandboxConfig()
            
            assert config.default_cpu_limit == 1000
            assert config.default_memory_limit == 512
            assert config.default_disk_limit == 1024
            assert config.default_network_enabled is True


class TestSandboxConfigValidation:
    """Test SandboxConfig validation."""

    def test_validation_requires_e2b_api_key(self):
        """Test that E2B provider requires API key."""
        with patch("backend.core.conf.settings") as mock_settings:
            mock_settings.REDIS_HOST = "localhost"
            mock_settings.REDIS_PORT = 6379
            mock_settings.REDIS_PASSWORD = ""
            mock_settings.REDIS_DATABASE = 0
            mock_settings.E2B_API_KEY = None  # No API key
            mock_settings.E2B_TEMPLATE_ID = "base"
            
            from backend.src.sandbox.sandbox_server.config import SandboxConfig
            
            with pytest.raises(ValueError) as excinfo:
                SandboxConfig(provider_type="e2b", e2b_api_key=None)
            
            assert "E2B API key is required" in str(excinfo.value)

    def test_validation_requires_redis_url_for_redis_queue(self):
        """Test that Redis queue provider requires redis_url."""
        with patch("backend.core.conf.settings") as mock_settings:
            mock_settings.REDIS_HOST = "localhost"
            mock_settings.REDIS_PORT = 6379
            mock_settings.REDIS_PASSWORD = ""
            mock_settings.REDIS_DATABASE = 0
            mock_settings.E2B_API_KEY = "test_key"
            mock_settings.E2B_TEMPLATE_ID = "base"
            
            from backend.src.sandbox.sandbox_server.config import SandboxConfig
            
            with pytest.raises(ValueError) as excinfo:
                SandboxConfig(queue_provider="redis", redis_url=None)
            
            assert "redis_url is required" in str(excinfo.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
