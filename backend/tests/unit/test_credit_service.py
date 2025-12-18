"""Tests for credit system functionality.

Tests cover:
- Credit balance querying
- Credit deduction (bonus credits first)
- Credit addition
- Session metrics tracking
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


class TestCreditBalance:
    """Tests for credit balance operations."""

    @pytest.mark.asyncio
    async def test_get_user_credits_returns_balance(self):
        """Test getting user credits returns proper CreditBalance object."""
        from backend.app.agent.service.credit_service import get_user_credits, CreditBalance
        
        # Mock database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock(
            credits=100.0,
            bonus_credits=50.0,
            last_login_time=datetime.now()
        )
        mock_session.execute.return_value = mock_result
        
        # Call the function
        result = await get_user_credits(db_session=mock_session, user_id=1)
        
        # Verify
        assert result is not None
        assert isinstance(result, CreditBalance)
        assert result.credits == 100.0
        assert result.bonus_credits == 50.0
        assert result.total_credits == 150.0

    @pytest.mark.asyncio
    async def test_get_user_credits_user_not_found(self):
        """Test getting credits for non-existent user returns None."""
        from backend.app.agent.service.credit_service import get_user_credits
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await get_user_credits(db_session=mock_session, user_id=999)
        
        assert result is None


class TestCreditDeduction:
    """Tests for credit deduction logic."""

    @pytest.mark.asyncio
    async def test_has_sufficient_credits_true(self):
        """Test sufficient credits check returns True when user has enough."""
        from backend.app.agent.service.credit_service import has_sufficient_credits, CreditBalance
        
        with patch('backend.app.agent.service.credit_service.get_user_credits') as mock_get:
            mock_get.return_value = CreditBalance(
                user_id=1,
                credits=100.0,
                bonus_credits=50.0,
                total_credits=150.0
            )
            
            mock_session = AsyncMock()
            result = await has_sufficient_credits(
                db_session=mock_session, user_id=1, amount=100.0
            )
            
            assert result is True

    @pytest.mark.asyncio
    async def test_has_sufficient_credits_false(self):
        """Test sufficient credits check returns False when user lacks credits."""
        from backend.app.agent.service.credit_service import has_sufficient_credits, CreditBalance
        
        with patch('backend.app.agent.service.credit_service.get_user_credits') as mock_get:
            mock_get.return_value = CreditBalance(
                user_id=1,
                credits=10.0,
                bonus_credits=5.0,
                total_credits=15.0
            )
            
            mock_session = AsyncMock()
            result = await has_sufficient_credits(
                db_session=mock_session, user_id=1, amount=100.0
            )
            
            assert result is False


class TestCreditAddition:
    """Tests for adding credits to user."""

    @pytest.mark.asyncio
    async def test_add_user_credits_regular(self):
        """Test adding regular credits to user."""
        from backend.app.agent.service.credit_service import add_user_credits
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock(credits=200.0, bonus_credits=50.0)
        mock_session.execute.return_value = mock_result
        
        result = await add_user_credits(
            db_session=mock_session, user_id=1, amount=100.0, is_bonus=False
        )
        
        assert result is True
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_user_credits_bonus(self):
        """Test adding bonus credits to user."""
        from backend.app.agent.service.credit_service import add_user_credits
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock(credits=100.0, bonus_credits=150.0)
        mock_session.execute.return_value = mock_result
        
        result = await add_user_credits(
            db_session=mock_session, user_id=1, amount=100.0, is_bonus=True
        )
        
        assert result is True


class TestSessionMetrics:
    """Tests for session metrics tracking."""

    @pytest.mark.asyncio
    async def test_accumulate_session_metrics_new_session(self):
        """Test accumulating metrics creates new record for new session."""
        from backend.app.agent.service.metrics_service import accumulate_session_metrics
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing record
        mock_session.execute.return_value = mock_result
        
        result = await accumulate_session_metrics(
            db_session=mock_session, session_id="test-session-123", credits=-10.0
        )
        
        # Should add new record
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_accumulate_session_metrics_existing_session(self):
        """Test accumulating metrics updates existing record."""
        from backend.app.agent.service.metrics_service import accumulate_session_metrics
        
        mock_session = AsyncMock()
        mock_record = MagicMock(credits=-5.0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_session.execute.return_value = mock_result
        
        result = await accumulate_session_metrics(
            db_session=mock_session, session_id="test-session-123", credits=-10.0
        )
        
        # Should update existing record
        assert mock_record.credits == -15.0  # -5.0 + (-10.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
