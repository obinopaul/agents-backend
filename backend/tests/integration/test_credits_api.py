"""Integration tests for credits API endpoints.

These tests require a running server or mock the FastAPI app.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from fastapi.testclient import TestClient


class TestCreditsAPI:
    """Integration tests for credits API endpoints."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request with user info."""
        request = MagicMock()
        request.user = MagicMock(id=1, username="testuser")
        return request

    @pytest.mark.asyncio
    async def test_get_credit_balance_endpoint(self, mock_request):
        """Test the GET /credits/balance endpoint."""
        from backend.app.agent.api.v1.credits import get_credit_balance
        from backend.app.agent.service.credit_service import CreditBalance
        
        mock_db = AsyncMock()
        
        with patch('backend.app.agent.api.v1.credits.get_user_credits') as mock_get:
            mock_get.return_value = CreditBalance(
                user_id=1,
                credits=100.0,
                bonus_credits=50.0,
                total_credits=150.0
            )
            
            result = await get_credit_balance(
                request=mock_request,
                db=mock_db
            )
            
            assert result.credits == 100.0
            assert result.bonus_credits == 50.0
            assert result.total_credits == 150.0

    @pytest.mark.asyncio
    async def test_get_credit_balance_not_found(self, mock_request):
        """Test credit balance for non-existent user raises 404."""
        from backend.app.agent.api.v1.credits import get_credit_balance
        from fastapi import HTTPException
        
        mock_db = AsyncMock()
        
        with patch('backend.app.agent.api.v1.credits.get_user_credits') as mock_get:
            mock_get.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await get_credit_balance(
                    request=mock_request,
                    db=mock_db
                )
            
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_credit_usage_endpoint(self, mock_request):
        """Test the GET /credits/usage endpoint."""
        from backend.app.agent.api.v1.credits import get_credit_usage
        from backend.app.agent.service.credit_service import CreditBalance
        
        mock_db = AsyncMock()
        
        with patch('backend.app.agent.api.v1.credits.get_user_credits') as mock_get, \
             patch('backend.app.agent.api.v1.credits.get_user_credit_history') as mock_history:
            
            mock_get.return_value = CreditBalance(
                user_id=1,
                credits=100.0,
                bonus_credits=50.0,
                total_credits=150.0
            )
            mock_history.return_value = ([], 0)  # Empty history
            
            result = await get_credit_usage(
                request=mock_request,
                db=mock_db,
                page=1,
                per_page=20
            )
            
            assert result.sessions == []
            assert result.total == 0


class TestToolServerDBIntegration:
    """Tests for tool server database integration."""

    @pytest.mark.asyncio
    async def test_get_user_by_api_key_integration(self):
        """Test tool server's get_user_by_api_key function."""
        from backend.src.tool_server.integrations.app.db import get_user_by_api_key
        
        # This will use the mocked database session
        with patch('backend.src.tool_server.integrations.app.db.async_db_session') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session
            
            with patch('backend.src.tool_server.integrations.app.db._get_user_by_api_key') as mock_inner:
                mock_user = MagicMock()
                mock_inner.return_value = mock_user
                
                result = await get_user_by_api_key("sk_test123")
                
                # Function should work without error
                # (actual result depends on mock configuration)

    @pytest.mark.asyncio
    async def test_apply_tool_usage_integration(self):
        """Test tool server's apply_tool_usage function."""
        from backend.src.tool_server.integrations.app.db import apply_tool_usage
        
        with patch('backend.src.tool_server.integrations.app.db.async_db_session') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session
            
            with patch('backend.src.tool_server.integrations.app.db._accumulate_session_metrics') as mock_metrics, \
                 patch('backend.src.tool_server.integrations.app.db._deduct_user_credits') as mock_deduct:
                
                mock_deduct.return_value = True
                
                result = await apply_tool_usage(
                    user_id="1",
                    session_id="test-session",
                    amount=5.0
                )
                
                # Should successfully apply usage


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
