"""
Credit Calculator

Calculates token costs for LLM usage based on model pricing.
Supports:
- Regular token costs (input/output)
- Cached token reads (reduced pricing)
- Cache write costs (creation)

Based on external_billing/credits/calculator.py.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Default pricing constants (fallback when model pricing unavailable)
TOKEN_PRICE_MULTIPLIER = Decimal('1.2')  # 20% markup
DEFAULT_INPUT_COST_PER_MILLION = Decimal('1.00')
DEFAULT_OUTPUT_COST_PER_MILLION = Decimal('3.00')
DEFAULT_CACHED_READ_MULTIPLIER = Decimal('0.1')  # 10% of input cost
DEFAULT_CACHE_WRITE_MULTIPLIER = Decimal('0.25')  # 25% of input cost
MINIMUM_COST = Decimal('0.0001')


class CreditCalculator:
    """
    Calculate credit costs for LLM operations.
    
    Uses model registry pricing when available, falls back to defaults.
    All costs include a configurable markup (TOKEN_PRICE_MULTIPLIER).
    
    Usage:
        calculator = CreditCalculator()
        cost = calculator.calculate_token_cost(
            prompt_tokens=1000,
            completion_tokens=500,
            model="gpt-4"
        )
    """
    
    def __init__(
        self,
        price_multiplier: Decimal = TOKEN_PRICE_MULTIPLIER,
        model_registry: Optional[Any] = None
    ):
        """
        Initialize the calculator.
        
        Args:
            price_multiplier: Markup to apply to raw costs
            model_registry: Optional model registry for pricing lookup
        """
        self.price_multiplier = Decimal(str(price_multiplier))
        self.model_registry = model_registry
        self._pricing_cache: Dict[str, Dict] = {}
    
    def calculate_token_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        cached_read_tokens: int = 0,
        cache_creation_tokens: int = 0
    ) -> Decimal:
        """
        Calculate total token cost for an LLM call.
        
        Args:
            prompt_tokens: Total input/prompt tokens (includes cached if applicable)
            completion_tokens: Output/completion tokens
            model: Model identifier
            cached_read_tokens: Tokens read from cache (subset of prompt_tokens)
            cache_creation_tokens: Tokens written to cache (subset of prompt_tokens)
            
        Returns:
            Total cost in dollars with markup applied
        """
        # Skip mock/test models
        if model in ("mock-ai", "test-model", "mock"):
            return Decimal('0')
        
        try:
            # Get pricing for model
            pricing = self._get_model_pricing(model)
            
            if pricing:
                return self._calculate_with_pricing(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cached_read_tokens=cached_read_tokens,
                    cache_creation_tokens=cache_creation_tokens,
                    pricing=pricing
                )
            
            # Fallback to default pricing
            logger.debug(f"[CALC] No pricing found for model '{model}', using defaults")
            return self._calculate_with_defaults(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_read_tokens=cached_read_tokens,
                cache_creation_tokens=cache_creation_tokens
            )
            
        except Exception as e:
            logger.error(f"[CALC] Error calculating token cost for '{model}': {e}")
            # Return minimum cost on error
            return MINIMUM_COST
    
    def calculate_cached_token_cost(self, cached_tokens: int, model: str) -> Decimal:
        """
        Calculate cost for cached token reads only.
        
        Cached reads are typically much cheaper than regular input tokens.
        
        Args:
            cached_tokens: Number of tokens read from cache
            model: Model identifier
            
        Returns:
            Cost in dollars with markup
        """
        if cached_tokens <= 0 or model in ("mock-ai", "test-model"):
            return Decimal('0')
        
        pricing = self._get_model_pricing(model)
        
        if pricing and 'cached_read_cost_per_million' in pricing:
            cost_per_million = Decimal(str(pricing['cached_read_cost_per_million']))
        else:
            # Fallback: 10% of standard input cost
            cost_per_million = DEFAULT_INPUT_COST_PER_MILLION * DEFAULT_CACHED_READ_MULTIPLIER
        
        cost = (Decimal(cached_tokens) / Decimal('1000000')) * cost_per_million * self.price_multiplier
        
        logger.debug(f"[CALC] Cached read: {cached_tokens} tokens @ ${cost_per_million}/M = ${cost:.6f}")
        
        return cost.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    
    def calculate_cache_write_cost(
        self,
        cache_creation_tokens: int,
        model: str,
        cache_ttl: str = "5m"
    ) -> Decimal:
        """
        Calculate cost for cache creation (writing to cache).
        
        Args:
            cache_creation_tokens: Tokens written to cache
            model: Model identifier
            cache_ttl: Cache time-to-live ("5m" or "1h")
            
        Returns:
            Cost in dollars with markup
        """
        if cache_creation_tokens <= 0 or model in ("mock-ai", "test-model"):
            return Decimal('0')
        
        pricing = self._get_model_pricing(model)
        
        # Select pricing based on TTL
        if cache_ttl == "1h":
            pricing_key = 'cache_write_1h_cost_per_million'
        else:
            pricing_key = 'cache_write_5m_cost_per_million'
        
        if pricing and pricing_key in pricing:
            cost_per_million = Decimal(str(pricing[pricing_key]))
        else:
            # Fallback: 25% of standard input cost
            cost_per_million = DEFAULT_INPUT_COST_PER_MILLION * DEFAULT_CACHE_WRITE_MULTIPLIER
        
        cost = (Decimal(cache_creation_tokens) / Decimal('1000000')) * cost_per_million * self.price_multiplier
        
        logger.debug(f"[CALC] Cache write ({cache_ttl}): {cache_creation_tokens} tokens @ ${cost_per_million}/M = ${cost:.6f}")
        
        return cost.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    
    def _get_model_pricing(self, model: str) -> Optional[Dict]:
        """Get pricing for a model from registry or cache."""
        # Check local cache first
        if model in self._pricing_cache:
            return self._pricing_cache[model]
        
        # Try model registry if available
        if self.model_registry:
            try:
                pricing = self.model_registry.get_pricing(model)
                if pricing:
                    pricing_dict = {
                        'input_cost_per_million': float(getattr(pricing, 'input_cost_per_million_tokens', DEFAULT_INPUT_COST_PER_MILLION)),
                        'output_cost_per_million': float(getattr(pricing, 'output_cost_per_million_tokens', DEFAULT_OUTPUT_COST_PER_MILLION)),
                        'cached_read_cost_per_million': float(getattr(pricing, 'cached_read_cost_per_million_tokens', 0)),
                        'cache_write_5m_cost_per_million': float(getattr(pricing, 'cache_write_5m_cost_per_million_tokens', 0)),
                        'cache_write_1h_cost_per_million': float(getattr(pricing, 'cache_write_1h_cost_per_million_tokens', 0)),
                    }
                    self._pricing_cache[model] = pricing_dict
                    return pricing_dict
            except Exception as e:
                logger.debug(f"[CALC] Failed to get pricing from registry for '{model}': {e}")
        
        # Try importing model_manager from project
        try:
            from backend.src.llms import model_manager
            pricing = model_manager.get_pricing(model)
            if pricing:
                pricing_dict = {
                    'input_cost_per_million': float(getattr(pricing, 'input_cost_per_million_tokens', DEFAULT_INPUT_COST_PER_MILLION)),
                    'output_cost_per_million': float(getattr(pricing, 'output_cost_per_million_tokens', DEFAULT_OUTPUT_COST_PER_MILLION)),
                    'cached_read_cost_per_million': float(getattr(pricing, 'cached_read_cost_per_million_tokens', 0)),
                    'cache_write_5m_cost_per_million': float(getattr(pricing, 'cache_write_5m_cost_per_million_tokens', 0)),
                    'cache_write_1h_cost_per_million': float(getattr(pricing, 'cache_write_1h_cost_per_million_tokens', 0)),
                }
                self._pricing_cache[model] = pricing_dict
                return pricing_dict
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"[CALC] Failed to get pricing from model_manager for '{model}': {e}")
        
        return None
    
    def _calculate_with_pricing(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cached_read_tokens: int,
        cache_creation_tokens: int,
        pricing: Dict
    ) -> Decimal:
        """Calculate cost using specific pricing."""
        input_cost_per_million = Decimal(str(pricing['input_cost_per_million']))
        output_cost_per_million = Decimal(str(pricing['output_cost_per_million']))
        
        # Calculate non-cached prompt tokens
        regular_prompt_tokens = prompt_tokens - cached_read_tokens - cache_creation_tokens
        regular_prompt_tokens = max(0, regular_prompt_tokens)
        
        # Regular input cost
        input_cost = (Decimal(regular_prompt_tokens) / Decimal('1000000')) * input_cost_per_million
        
        # Output cost
        output_cost = (Decimal(completion_tokens) / Decimal('1000000')) * output_cost_per_million
        
        # Cached read cost (if applicable)
        cached_read_cost = Decimal('0')
        if cached_read_tokens > 0:
            cached_read_per_million = Decimal(str(pricing.get('cached_read_cost_per_million', 0)))
            if cached_read_per_million > 0:
                cached_read_cost = (Decimal(cached_read_tokens) / Decimal('1000000')) * cached_read_per_million
            else:
                # Fallback: 10% of input cost
                cached_read_cost = (Decimal(cached_read_tokens) / Decimal('1000000')) * input_cost_per_million * DEFAULT_CACHED_READ_MULTIPLIER
        
        # Cache write cost (if applicable)
        cache_write_cost = Decimal('0')
        if cache_creation_tokens > 0:
            cache_write_per_million = Decimal(str(pricing.get('cache_write_5m_cost_per_million', 0)))
            if cache_write_per_million > 0:
                cache_write_cost = (Decimal(cache_creation_tokens) / Decimal('1000000')) * cache_write_per_million
            else:
                # Fallback: 25% of input cost
                cache_write_cost = (Decimal(cache_creation_tokens) / Decimal('1000000')) * input_cost_per_million * DEFAULT_CACHE_WRITE_MULTIPLIER
        
        # Total with markup
        total = (input_cost + output_cost + cached_read_cost + cache_write_cost) * self.price_multiplier
        
        logger.debug(
            f"[CALC] Cost breakdown: input=${input_cost:.6f}, output=${output_cost:.6f}, "
            f"cached_read=${cached_read_cost:.6f}, cache_write=${cache_write_cost:.6f}, "
            f"total (with {self.price_multiplier}x markup)=${total:.6f}"
        )
        
        return total.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    
    def _calculate_with_defaults(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        cached_read_tokens: int,
        cache_creation_tokens: int
    ) -> Decimal:
        """Calculate cost using default pricing."""
        regular_prompt_tokens = prompt_tokens - cached_read_tokens - cache_creation_tokens
        regular_prompt_tokens = max(0, regular_prompt_tokens)
        
        # Regular tokens
        input_cost = (Decimal(regular_prompt_tokens) / Decimal('1000000')) * DEFAULT_INPUT_COST_PER_MILLION
        output_cost = (Decimal(completion_tokens) / Decimal('1000000')) * DEFAULT_OUTPUT_COST_PER_MILLION
        
        # Cached reads at discounted rate
        cached_read_cost = (Decimal(cached_read_tokens) / Decimal('1000000')) * DEFAULT_INPUT_COST_PER_MILLION * DEFAULT_CACHED_READ_MULTIPLIER
        
        # Cache writes
        cache_write_cost = (Decimal(cache_creation_tokens) / Decimal('1000000')) * DEFAULT_INPUT_COST_PER_MILLION * DEFAULT_CACHE_WRITE_MULTIPLIER
        
        total = (input_cost + output_cost + cached_read_cost + cache_write_cost) * self.price_multiplier
        
        return total.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    
    def estimate_cost(
        self,
        estimated_tokens: int,
        model: str,
        input_output_ratio: float = 0.7
    ) -> Decimal:
        """
        Estimate cost for a given number of total tokens.
        
        Useful for pre-flight checks before expensive operations.
        
        Args:
            estimated_tokens: Total estimated tokens (input + output)
            model: Model identifier
            input_output_ratio: Ratio of input to total (default 0.7 = 70% input)
            
        Returns:
            Estimated cost in dollars
        """
        prompt_tokens = int(estimated_tokens * input_output_ratio)
        completion_tokens = estimated_tokens - prompt_tokens
        
        return self.calculate_token_cost(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model
        )


# Global instance
credit_calculator = CreditCalculator()


# Convenience functions
def calculate_token_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    cached_read_tokens: int = 0,
    cache_creation_tokens: int = 0
) -> Decimal:
    """Calculate token cost for an LLM call."""
    return credit_calculator.calculate_token_cost(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=model,
        cached_read_tokens=cached_read_tokens,
        cache_creation_tokens=cache_creation_tokens
    )


def calculate_cached_token_cost(cached_tokens: int, model: str) -> Decimal:
    """Calculate cost for cached token reads."""
    return credit_calculator.calculate_cached_token_cost(cached_tokens, model)


def calculate_cache_write_cost(cache_creation_tokens: int, model: str, cache_ttl: str = "5m") -> Decimal:
    """Calculate cost for cache creation."""
    return credit_calculator.calculate_cache_write_cost(cache_creation_tokens, model, cache_ttl)


def estimate_cost(estimated_tokens: int, model: str) -> Decimal:
    """Estimate cost for a given number of tokens."""
    return credit_calculator.estimate_cost(estimated_tokens, model)
