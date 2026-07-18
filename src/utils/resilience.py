"""
Retry logic with exponential backoff and circuit breaker pattern for external services.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar

from src.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for external service calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "default",
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._last_failure_time:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    async def record_success(self) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= 2:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' closed - service recovered")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = max(0, self._failure_count - 1)

    async def record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            self._success_count = 0

            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' opened after {self._failure_count} failures"
                )

    def is_allowed(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True
        return False

    def get_retry_after(self) -> int:
        if self._last_failure_time:
            elapsed = time.time() - self._last_failure_time
            remaining = max(0, self.recovery_timeout - elapsed)
            return int(remaining) + 1
        return self.recovery_timeout


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions


async def retry_with_backoff(
    func: Callable[..., Any],
    *args: Any,
    config: RetryConfig | None = None,
    circuit_breaker: CircuitBreaker | None = None,
    **kwargs: Any,
) -> Any:
    """
    Execute a function with retry logic and exponential backoff.
    Optionally uses a circuit breaker.
    """
    if config is None:
        config = RetryConfig()

    last_exception = None

    for attempt in range(1, config.max_attempts + 1):
        if circuit_breaker and not circuit_breaker.is_allowed():
            from src.api.error_handlers import CircuitBreakerOpenError

            raise CircuitBreakerOpenError(
                service=circuit_breaker.name,
                retry_after_seconds=circuit_breaker.get_retry_after(),
            )

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            if circuit_breaker:
                await circuit_breaker.record_success()

            return result

        except config.retryable_exceptions as e:
            last_exception = e

            if circuit_breaker:
                await circuit_breaker.record_failure()

            if attempt == config.max_attempts:
                logger.error(
                    f"All {config.max_attempts} attempts failed",
                    extra={"error": str(e), "exception_type": type(e).__name__},
                )
                raise

            delay = min(
                config.base_delay * (config.exponential_base ** (attempt - 1)),
                config.max_delay,
            )
            logger.warning(
                f"Attempt {attempt}/{config.max_attempts} failed, retrying in {delay:.1f}s",
                extra={"error": str(e)},
            )
            await asyncio.sleep(delay)

    if last_exception is not None:
        raise last_exception
    raise RuntimeError("Unexpected end of retry loop")


def create_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
) -> CircuitBreaker:
    """Create a circuit breaker for an external service."""
    return CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
    )


# Pre-configured circuit breakers for common services
groq_circuit_breaker = create_circuit_breaker("groq", failure_threshold=3, recovery_timeout=30)
tavily_circuit_breaker = create_circuit_breaker("tavily", failure_threshold=5, recovery_timeout=60)
serper_circuit_breaker = create_circuit_breaker("serper", failure_threshold=5, recovery_timeout=60)
supabase_circuit_breaker = create_circuit_breaker(
    "supabase", failure_threshold=3, recovery_timeout=30
)
