"""Tests for LLM metrics service functionality.

Tests cover:
- Model pricing lookup
- Credit calculation from tokens
- LLM usage tracking
- Session metrics operations
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestModelPricing:
    """Tests for model pricing database."""

    def test_get_model_pricing_exact_match(self):
        """Test getting pricing for exact model name match."""
        from backend.app.agent.service.metrics_service import get_model_pricing
        
        pricing = get_model_pricing("gpt-4o")
        
        assert pricing.model_name == "gpt-4o"
        assert pricing.input_price_per_million == 2.50
        assert pricing.output_price_per_million == 10.00

    def test_get_model_pricing_partial_match(self):
        """Test getting pricing for model with version suffix."""
        from backend.app.agent.service.metrics_service import get_model_pricing
        
        pricing = get_model_pricing("gpt-4o-2024-05-13")
        
        # Should match gpt-4o
        assert pricing.input_price_per_million == 2.50

    def test_get_model_pricing_unknown_model(self):
        """Test getting pricing for unknown model returns default."""
        from backend.app.agent.service.metrics_service import get_model_pricing, DEFAULT_PRICING
        
        pricing = get_model_pricing("unknown-model-xyz")
        
        assert pricing.model_name == DEFAULT_PRICING.model_name
        assert pricing.input_price_per_million == DEFAULT_PRICING.input_price_per_million

    def test_model_pricing_database_count(self):
        """Test that MODEL_PRICING has expected number of models."""
        from backend.app.agent.service.metrics_service import MODEL_PRICING
        
        assert len(MODEL_PRICING) >= 10  # At least 10 models configured


class TestCreditCalculation:
    """Tests for credit calculation from token usage."""

    def test_calculate_credits_basic(self):
        """Test basic credit calculation."""
        from backend.app.agent.service.metrics_service import calculate_credits_from_tokens
        
        # gpt-4o: $2.50/M input, $10.00/M output
        credits = calculate_credits_from_tokens(
            prompt_tokens=1000,
            completion_tokens=1000,
            model_name="gpt-4o",
        )
        
        # Expected: (1000/1M * 2.50) + (1000/1M * 10.00) = 0.0025 + 0.01 = 0.0125
        assert abs(credits - 0.0125) < 0.0001

    def test_calculate_credits_with_cache(self):
        """Test credit calculation with cache read tokens."""
        from backend.app.agent.service.metrics_service import calculate_credits_from_tokens
        
        # gpt-4o: cache read is $1.25/M
        credits = calculate_credits_from_tokens(
            prompt_tokens=1000,
            completion_tokens=0,
            model_name="gpt-4o",
            cache_read_tokens=800,  # 800 from cache, 200 not cached
        )
        
        # Non-cached: 200/1M * 2.50 = 0.0005
        # Cache read: 800/1M * 1.25 = 0.001
        expected = 0.0005 + 0.001
        assert abs(credits - expected) < 0.0001

    def test_calculate_credits_gpt4o_mini(self):
        """Test credit calculation for cheap model."""
        from backend.app.agent.service.metrics_service import calculate_credits_from_tokens
        
        # gpt-4o-mini: $0.15/M input, $0.60/M output
        credits = calculate_credits_from_tokens(
            prompt_tokens=10000,
            completion_tokens=5000,
            model_name="gpt-4o-mini",
        )
        
        # Expected: (10000/1M * 0.15) + (5000/1M * 0.60) = 0.0015 + 0.003 = 0.0045
        assert abs(credits - 0.0045) < 0.0001

    def test_calculate_credits_zero_tokens(self):
        """Test credit calculation with zero tokens."""
        from backend.app.agent.service.metrics_service import calculate_credits_from_tokens
        
        credits = calculate_credits_from_tokens(
            prompt_tokens=0,
            completion_tokens=0,
            model_name="gpt-4o",
        )
        
        assert credits == 0.0


class TestTrackLLMUsage:
    """Tests for track_llm_usage function."""

    @pytest.mark.asyncio
    async def test_track_llm_usage_new_session(self):
        """Test tracking LLM usage creates new session record."""
        from backend.app.agent.service.metrics_service import track_llm_usage
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing session
        mock_session.execute.return_value = mock_result
        
        with patch('backend.app.agent.service.metrics_service.deduct_user_credits') as mock_deduct:
            mock_deduct.return_value = True
            
            credits = await track_llm_usage(
                db_session=mock_session,
                user_id=1,
                session_id="new-session-123",
                prompt_tokens=500,
                completion_tokens=200,
                model_name="gpt-4o",
            )
        
        # Should create new record
        mock_session.add.assert_called_once()
        assert credits is not None
        assert credits > 0

    @pytest.mark.asyncio
    async def test_track_llm_usage_existing_session(self):
        """Test tracking LLM usage updates existing session."""
        from backend.app.agent.service.metrics_service import track_llm_usage
        
        mock_session = AsyncMock()
        mock_record = MagicMock(
            total_prompt_tokens=100,
            total_completion_tokens=50,
            credits=0.01,
            model_name="gpt-4o",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_session.execute.return_value = mock_result
        
        with patch('backend.app.agent.service.metrics_service.deduct_user_credits') as mock_deduct:
            mock_deduct.return_value = True
            
            await track_llm_usage(
                db_session=mock_session,
                user_id=1,
                session_id="existing-session",
                prompt_tokens=500,
                completion_tokens=200,
                model_name="gpt-4o",
            )
        
        # Should update existing record
        assert mock_record.total_prompt_tokens == 600  # 100 + 500
        assert mock_record.total_completion_tokens == 250  # 50 + 200

    @pytest.mark.asyncio
    async def test_track_llm_usage_deducts_credits(self):
        """Test that track_llm_usage calls deduct_user_credits."""
        from backend.app.agent.service.metrics_service import track_llm_usage
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        with patch('backend.app.agent.service.metrics_service.deduct_user_credits') as mock_deduct:
            mock_deduct.return_value = True
            
            await track_llm_usage(
                db_session=mock_session,
                user_id=1,
                session_id="test",
                prompt_tokens=1000,
                completion_tokens=500,
                model_name="gpt-4o",
            )
            
            # Verify deduct was called with correct arguments
            mock_deduct.assert_called_once()
            call_args = mock_deduct.call_args
            assert call_args.kwargs['user_id'] == 1
            assert call_args.kwargs['amount'] > 0


class TestGetSessionMetrics:
    """Tests for get_session_metrics function."""

    @pytest.mark.asyncio
    async def test_get_session_metrics_found(self):
        """Test getting metrics for existing session."""
        from backend.app.agent.service.metrics_service import get_session_metrics
        
        mock_session = AsyncMock()
        mock_record = MagicMock(
            session_id="test-123",
            user_id=1,
            model_name="gpt-4o",
            credits=0.05,
            total_prompt_tokens=1000,
            total_completion_tokens=500,
            created_at=None,
            updated_at=None,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_record
        mock_session.execute.return_value = mock_result
        
        result = await get_session_metrics(db_session=mock_session, session_id="test-123")
        
        assert result is not None
        assert result["session_id"] == "test-123"
        assert result["credits"] == 0.05

    @pytest.mark.asyncio
    async def test_get_session_metrics_not_found(self):
        """Test getting metrics for non-existent session."""
        from backend.app.agent.service.metrics_service import get_session_metrics
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await get_session_metrics(db_session=mock_session, session_id="nonexistent")
        
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
