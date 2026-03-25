"""
Stripe Circuit Breaker

Implements the circuit breaker pattern for Stripe API calls to prevent
cascading failures when Stripe is experiencing issues.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Stripe is failing, block requests to prevent overload
- HALF_OPEN: Testing if Stripe has recovered

Based on external_billing/external/stripe/client.py.
"""

import asyncio
from typing import Any, Callable, Dict, Optional
from datetime import datetime, timezone
from enum import Enum
import logging

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


class StripeCircuitBreaker:
    """
    Circuit breaker for Stripe API calls.
    
    Prevents cascading failures when Stripe is experiencing issues.
    Uses database persistence for multi-instance consistency.
    
    Usage:
        breaker = StripeCircuitBreaker()
        result = await breaker.safe_call(stripe.Customer.create_async, email="...")
    """
    
    def __init__(
        self,
        circuit_name: str = "stripe_api",
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = None
    ):
        """
        Initialize the circuit breaker.
        
        Args:
            circuit_name: Unique name for this circuit
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery
            expected_exception: Exception type to catch (default: stripe.StripeError)
        """
        self.circuit_name = circuit_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._lock = asyncio.Lock()
        
        # Import stripe here to handle optional dependency
        try:
            import stripe
            self.expected_exception = expected_exception or stripe.StripeError
        except ImportError:
            self.expected_exception = Exception
    
    async def safe_call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a Stripe API call with circuit breaker protection.
        
        Args:
            func: Async Stripe API function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result from the Stripe API call
            
        Raises:
            Exception: If circuit is open or API call fails
        """
        async with self._lock:
            state_info = await self._get_circuit_state()
            
            if await self._should_allow_request(state_info):
                try:
                    result = await func(*args, **kwargs)
                    await self._record_success()
                    return result
                except self.expected_exception as e:
                    await self._record_failure(str(e))
                    raise
                except Exception as e:
                    logger.error(f"[CIRCUIT BREAKER] Unexpected error in {func.__name__}: {e}")
                    raise
            else:
                state_value = state_info['state'].value if isinstance(state_info['state'], CircuitState) else state_info['state']
                logger.warning(f"[CIRCUIT BREAKER] Request blocked - circuit is {state_value}")
                raise Exception(f"Circuit breaker is {state_value} - blocking request to Stripe API")
    
    async def get_status(self) -> Dict:
        """
        Get current circuit breaker status.
        
        Returns:
            Dictionary with circuit state and metrics
        """
        state_info = await self._get_circuit_state()
        state_value = state_info['state'].value if isinstance(state_info['state'], CircuitState) else state_info['state']
        
        return {
            'circuit_name': self.circuit_name,
            'state': state_value,
            'failure_count': state_info['failure_count'],
            'last_failure_time': state_info['last_failure_time'].isoformat() if state_info['last_failure_time'] else None,
            'failure_threshold': self.failure_threshold,
            'recovery_timeout': self.recovery_timeout,
            'status': '✅ Healthy' if state_info['state'] == CircuitState.CLOSED else f"🔴 {state_value.upper()}"
        }
    
    async def _get_circuit_state(self) -> Dict:
        """Get current circuit state from database."""
        try:
            from backend.database.db import async_db_session
            
            async with async_db_session() as session:
                from sqlalchemy import text
                
                result = await session.execute(
                    text("""
                        SELECT state, failure_count, last_failure_time 
                        FROM circuit_breaker_state 
                        WHERE circuit_name = :circuit_name
                    """),
                    {"circuit_name": self.circuit_name}
                )
                row = result.fetchone()
                
                if row:
                    last_failure_time = None
                    if row.last_failure_time:
                        if isinstance(row.last_failure_time, str):
                            last_failure_time = datetime.fromisoformat(row.last_failure_time.replace('Z', '+00:00'))
                        else:
                            last_failure_time = row.last_failure_time
                    
                    return {
                        'state': CircuitState(row.state),
                        'failure_count': row.failure_count,
                        'last_failure_time': last_failure_time
                    }
            
            # Initialize if not found
            await self._initialize_circuit_state()
            return {
                'state': CircuitState.CLOSED,
                'failure_count': 0,
                'last_failure_time': None
            }
            
        except Exception as e:
            logger.error(f"[CIRCUIT BREAKER] Error reading state from DB: {e}, defaulting to CLOSED")
            return {
                'state': CircuitState.CLOSED,
                'failure_count': 0,
                'last_failure_time': None
            }
    
    async def _should_allow_request(self, state_info: Dict) -> bool:
        """Determine if a request should be allowed based on circuit state."""
        state = state_info['state']
        
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.OPEN:
            if state_info['last_failure_time']:
                time_since_failure = datetime.now(timezone.utc) - state_info['last_failure_time']
                if time_since_failure.total_seconds() >= self.recovery_timeout:
                    await self._transition_to_half_open()
                    return True
            return False
        elif state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    async def _record_success(self):
        """Record a successful API call - reset circuit to closed."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO circuit_breaker_state (circuit_name, state, failure_count, success_count, last_success_time, updated_at)
                        VALUES (:circuit_name, :state, 0, 1, :now, :now)
                        ON CONFLICT (circuit_name) DO UPDATE SET
                            state = :state,
                            failure_count = 0,
                            success_count = circuit_breaker_state.success_count + 1,
                            last_success_time = :now,
                            updated_at = :now
                    """),
                    {
                        "circuit_name": self.circuit_name,
                        "state": CircuitState.CLOSED.value,
                        "now": datetime.now(timezone.utc)
                    }
                )
                await session.commit()
                
            logger.debug(f"[CIRCUIT BREAKER] Recorded success for {self.circuit_name}")
        except Exception as e:
            logger.error(f"[CIRCUIT BREAKER] Failed to record success: {e}")
    
    async def _record_failure(self, error_message: str):
        """Record a failed API call - may open circuit if threshold reached."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            state_info = await self._get_circuit_state()
            new_failure_count = state_info['failure_count'] + 1
            
            new_state = CircuitState.OPEN if new_failure_count >= self.failure_threshold else CircuitState.CLOSED
            
            async with async_db_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO circuit_breaker_state (circuit_name, state, failure_count, last_failure_time, updated_at)
                        VALUES (:circuit_name, :state, :failure_count, :now, :now)
                        ON CONFLICT (circuit_name) DO UPDATE SET
                            state = :state,
                            failure_count = :failure_count,
                            last_failure_time = :now,
                            updated_at = :now
                    """),
                    {
                        "circuit_name": self.circuit_name,
                        "state": new_state.value,
                        "failure_count": new_failure_count,
                        "now": datetime.now(timezone.utc)
                    }
                )
                await session.commit()
            
            if new_state == CircuitState.OPEN:
                logger.warning(f"[CIRCUIT BREAKER] Circuit opened due to {new_failure_count} failures: {error_message}")
            else:
                logger.debug(f"[CIRCUIT BREAKER] Recorded failure #{new_failure_count} for {self.circuit_name}")
                
        except Exception as e:
            logger.error(f"[CIRCUIT BREAKER] Failed to record failure: {e}")
    
    async def _transition_to_half_open(self):
        """Transition circuit to half-open state for testing."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            async with async_db_session() as session:
                await session.execute(
                    text("""
                        UPDATE circuit_breaker_state 
                        SET state = :state, failure_count = 0, updated_at = :now
                        WHERE circuit_name = :circuit_name
                    """),
                    {
                        "circuit_name": self.circuit_name,
                        "state": CircuitState.HALF_OPEN.value,
                        "now": datetime.now(timezone.utc)
                    }
                )
                await session.commit()
                
            logger.info(f"[CIRCUIT BREAKER] Transitioned {self.circuit_name} to half-open")
        except Exception as e:
            logger.error(f"[CIRCUIT BREAKER] Failed to transition to half-open: {e}")
    
    async def _initialize_circuit_state(self):
        """Initialize circuit state in database."""
        try:
            from backend.database.db import async_db_session
            from sqlalchemy import text
            
            now = datetime.now(timezone.utc)
            
            async with async_db_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO circuit_breaker_state (circuit_name, state, failure_count, success_count, created_at, updated_at)
                        VALUES (:circuit_name, :state, 0, 0, :now, :now)
                        ON CONFLICT (circuit_name) DO NOTHING
                    """),
                    {
                        "circuit_name": self.circuit_name,
                        "state": CircuitState.CLOSED.value,
                        "now": now
                    }
                )
                await session.commit()
                
            logger.info(f"[CIRCUIT BREAKER] Initialized circuit state for {self.circuit_name}")
        except Exception as e:
            logger.error(f"[CIRCUIT BREAKER] Failed to initialize state: {e}")


# Global circuit breaker instance
stripe_circuit_breaker = StripeCircuitBreaker()
