"""Tests for API key authentication and management.

Tests cover:
- API key creation
- API key validation
- API key revocation
- User lookup by API key
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


class TestAPIKeyCreation:
    """Tests for API key creation."""

    @pytest.mark.asyncio
    async def test_create_api_key_success(self):
        """Test creating an API key for a user."""
        from backend.app.agent.service.api_key_service import create_api_key
        
        mock_session = AsyncMock()
        
        result = await create_api_key(
            db_session=mock_session, user_id=1, name="Test Key"
        )
        
        # Should add the key to session
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_api_key_with_expiration(self):
        """Test creating an API key with expiration date."""
        from backend.app.agent.service.api_key_service import create_api_key
        
        mock_session = AsyncMock()
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        
        result = await create_api_key(
            db_session=mock_session, user_id=1, name="Temp Key", expires_at=expires
        )
        
        mock_session.add.assert_called_once()


class TestAPIKeyValidation:
    """Tests for API key validation."""

    @pytest.mark.asyncio
    async def test_get_user_by_api_key_valid(self):
        """Test getting user by valid API key."""
        from backend.app.agent.service.api_key_service import get_user_by_api_key
        
        mock_session = AsyncMock()
        mock_user = MagicMock(status=1)  # Active user
        mock_api_key = MagicMock(
            api_key="sk_test123",
            is_active=True,
            expires_at=None,
            user=mock_user,
            last_used_at=None
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_session.execute.return_value = mock_result
        
        result = await get_user_by_api_key(db_session=mock_session, api_key="sk_test123")
        
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_user_by_api_key_invalid(self):
        """Test getting user by invalid API key returns None."""
        from backend.app.agent.service.api_key_service import get_user_by_api_key
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await get_user_by_api_key(db_session=mock_session, api_key="invalid_key")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_api_key_expired(self):
        """Test expired API key returns None."""
        from backend.app.agent.service.api_key_service import get_user_by_api_key
        
        mock_session = AsyncMock()
        mock_user = MagicMock(status=1)
        expired_time = datetime.now(timezone.utc) - timedelta(days=1)
        mock_api_key = MagicMock(
            api_key="sk_expired",
            is_active=True,
            expires_at=expired_time,
            user=mock_user
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_session.execute.return_value = mock_result
        
        result = await get_user_by_api_key(db_session=mock_session, api_key="sk_expired")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_api_key_inactive_user(self):
        """Test API key for inactive user returns None."""
        from backend.app.agent.service.api_key_service import get_user_by_api_key
        
        mock_session = AsyncMock()
        mock_user = MagicMock(status=0)  # Inactive user
        mock_api_key = MagicMock(
            api_key="sk_inactive_user",
            is_active=True,
            expires_at=None,
            user=mock_user
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_session.execute.return_value = mock_result
        
        result = await get_user_by_api_key(db_session=mock_session, api_key="sk_inactive_user")
        
        assert result is None


class TestAPIKeyManagement:
    """Tests for API key management operations."""

    @pytest.mark.asyncio
    async def test_revoke_api_key_success(self):
        """Test revoking an API key."""
        from backend.app.agent.service.api_key_service import revoke_api_key
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock(id=1)  # Key found and revoked
        mock_session.execute.return_value = mock_result
        
        result = await revoke_api_key(db_session=mock_session, key_id=1, user_id=1)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_api_key_not_found(self):
        """Test revoking non-existent key returns False."""
        from backend.app.agent.service.api_key_service import revoke_api_key
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None  # Key not found
        mock_session.execute.return_value = mock_result
        
        result = await revoke_api_key(db_session=mock_session, key_id=999, user_id=1)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_get_user_api_keys(self):
        """Test getting all API keys for a user."""
        from backend.app.agent.service.api_key_service import get_user_api_keys
        
        mock_session = AsyncMock()
        mock_keys = [MagicMock(id=1), MagicMock(id=2)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_keys
        mock_session.execute.return_value = mock_result
        
        result = await get_user_api_keys(db_session=mock_session, user_id=1)
        
        assert len(result) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
