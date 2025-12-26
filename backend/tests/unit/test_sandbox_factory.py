"""
Unit tests for SandboxFactory.

Tests the factory pattern for creating sandbox providers (E2B, Daytona).
"""

import pytest
from unittest.mock import MagicMock, patch


class TestSandboxFactory:
    """Test SandboxFactory provider creation and registration."""

    def test_get_e2b_provider(self):
        """Test getting E2B provider class."""
        from backend.src.sandbox.sandbox_server.sandboxes.sandbox_factory import SandboxFactory
        from backend.src.sandbox.sandbox_server.sandboxes.e2b import E2BSandbox
        
        provider = SandboxFactory.get_provider("e2b")
        assert provider == E2BSandbox

    def test_get_daytona_provider(self):
        """Test getting Daytona provider class."""
        from backend.src.sandbox.sandbox_server.sandboxes.sandbox_factory import SandboxFactory
        from backend.src.sandbox.sandbox_server.sandboxes.daytona import DaytonaSandbox
        
        provider = SandboxFactory.get_provider("daytona")
        assert provider == DaytonaSandbox

    def test_get_default_provider_from_env(self):
        """Test getting default provider from environment variable."""
        with patch.dict("os.environ", {"SANDBOX_PROVIDER": "e2b"}):
            from backend.src.sandbox.sandbox_server.sandboxes.sandbox_factory import SandboxFactory
            from backend.src.sandbox.sandbox_server.sandboxes.e2b import E2BSandbox
            
            provider = SandboxFactory.get_provider(None)
            assert provider == E2BSandbox

    def test_invalid_provider_raises(self):
        """Test that requesting an unknown provider raises ValueError."""
        from backend.src.sandbox.sandbox_server.sandboxes.sandbox_factory import SandboxFactory
        
        with pytest.raises(ValueError) as excinfo:
            SandboxFactory.get_provider("unknown_provider")
        
        assert "Unsupported provider type" in str(excinfo.value)
        assert "unknown_provider" in str(excinfo.value)

    def test_register_custom_provider(self):
        """Test registering and retrieving a custom provider."""
        from backend.src.sandbox.sandbox_server.sandboxes.sandbox_factory import SandboxFactory
        from backend.src.sandbox.sandbox_server.sandboxes.base import BaseSandbox
        
        # Create a mock custom provider
        class CustomSandbox(BaseSandbox):
            pass
        
        # Register it
        SandboxFactory.register_provider("custom", CustomSandbox)
        
        # Retrieve it
        provider = SandboxFactory.get_provider("custom")
        assert provider == CustomSandbox
        
        # Clean up - remove from registry to not affect other tests
        del SandboxFactory._providers["custom"]

    def test_register_invalid_provider_raises(self):
        """Test that registering a non-BaseSandbox class raises ValueError."""
        from backend.src.sandbox.sandbox_server.sandboxes.sandbox_factory import SandboxFactory
        
        class NotASandbox:
            pass
        
        with pytest.raises(ValueError) as excinfo:
            SandboxFactory.register_provider("invalid", NotASandbox)
        
        assert "must inherit from" in str(excinfo.value)

    def test_get_available_providers(self):
        """Test getting list of available providers."""
        from backend.src.sandbox.sandbox_server.sandboxes.sandbox_factory import SandboxFactory
        
        providers = SandboxFactory.get_available_providers()
        
        assert "e2b" in providers
        assert "daytona" in providers
        assert isinstance(providers, list)


class TestSandboxProviderBase:
    """Test BaseSandbox abstract class structure."""

    def test_base_sandbox_is_abstract(self):
        """Test that BaseSandbox cannot be instantiated directly."""
        from backend.src.sandbox.sandbox_server.sandboxes.base import BaseSandbox
        
        # BaseSandbox should not be directly instantiable
        with pytest.raises(TypeError):
            BaseSandbox()

    def test_base_sandbox_required_methods(self):
        """Test that BaseSandbox defines required abstract methods."""
        from backend.src.sandbox.sandbox_server.sandboxes.base import BaseSandbox
        
        # Check for expected methods (abstract or not)
        expected_methods = [
            'create', 'connect', 'run_cmd', 'write_file', 'read_file',
            'expose_port', 'upload_file', 'download_file', 'create_directory'
        ]
        for method in expected_methods:
            assert hasattr(BaseSandbox, method), f"Expected method '{method}' not found in BaseSandbox"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
