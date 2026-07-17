"""
Langfuse tracing integration.
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any

try:
    from langfuse import Langfuse
    from langfuse.decorators import langfuse_context, observe
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    Langfuse = None
    langfuse_context = None
    observe = None

from src.config import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Tracing:
    """Langfuse tracing wrapper."""

    def __init__(self):
        self._client: Langfuse | None = None
        self._enabled = False

    @property
    def client(self) -> Langfuse | None:
        """Get or create Langfuse client."""
        if self._client is None and LANGFUSE_AVAILABLE:
            settings = get_settings()
            if settings.observability.langfuse_public_key and settings.observability.langfuse_secret_key:
                try:
                    self._client = Langfuse(
                        public_key=settings.observability.langfuse_public_key,
                        secret_key=settings.observability.langfuse_secret_key,
                        host=settings.observability.langfuse_host,
                    )
                    self._enabled = True
                    logger.info("Langfuse tracing initialized")
                except Exception as e:
                    logger.warning(f"Failed to initialize Langfuse: {e}")
                    self._enabled = False
            else:
                logger.debug("Langfuse keys not configured, tracing disabled")
        return self._client

    @property
    def enabled(self) -> bool:
        """Check if tracing is enabled."""
        return self._enabled and self.client is not None

    def flush(self):
        """Flush pending traces."""
        if self.client:
            self.client.flush()

    def trace(self, name: str, **kwargs) -> Any:
        """Create a new trace."""
        if not self.enabled:
            return NullTrace()

        return self.client.trace(name=name, **kwargs)

    def generation(
        self,
        trace_id: str,
        name: str,
        model: str,
        input: Any,
        output: Any = None,
        **kwargs,
    ) -> Any:
        """Record a generation."""
        if not self.enabled:
            return NullGeneration()

        return self.client.generation(
            trace_id=trace_id,
            name=name,
            model=model,
            input=input,
            output=output,
            **kwargs,
        )

    def span(self, trace_id: str, name: str, **kwargs) -> Any:
        """Create a span within a trace."""
        if not self.enabled:
            return NullSpan()

        return self.client.span(trace_id=trace_id, name=name, **kwargs)

    def event(self, trace_id: str, name: str, **kwargs) -> Any:
        """Record an event."""
        if not self.enabled:
            return

        self.client.event(trace_id=trace_id, name=name, **kwargs)

    def score(self, trace_id: str, name: str, value: float, **kwargs) -> Any:
        """Record a score."""
        if not self.enabled:
            return

        self.client.score(trace_id=trace_id, name=name, value=value, **kwargs)


class NullTrace:
    """Null object for disabled tracing."""

    def __init__(self):
        self.id = "disabled"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def generation(self, *args, **kwargs):
        return NullGeneration()

    def span(self, *args, **kwargs):
        return NullSpan()

    def event(self, *args, **kwargs):
        pass

    def score(self, *args, **kwargs):
        pass


class NullGeneration:
    """Null object for disabled generation."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def end(self, *args, **kwargs):
        pass


class NullSpan:
    """Null object for disabled span."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def end(self, *args, **kwargs):
        pass


# Global tracing instance
_tracing: Tracing | None = None


def get_tracing() -> Tracing:
    """Get global tracing instance."""
    global _tracing
    if _tracing is None:
        _tracing = Tracing()
    return _tracing


# Decorators for easy tracing
def trace_agent(agent_name: str):
    """Decorator to trace agent execution."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracing = get_tracing()
            if not tracing.enabled:
                return func(*args, **kwargs)

            trace = tracing.trace(name=f"agent.{agent_name}")
            try:
                with tracing.generation(
                    trace_id=trace.id,
                    name=f"{agent_name}.execute",
                    model=kwargs.get("model", "unknown"),
                    input={"args": str(args)[:500], "kwargs": str(kwargs)[:500]},
                ) as generation:
                    result = func(*args, **kwargs)
                    generation.end(output=str(result)[:1000])
                    return result
            except Exception as e:
                trace.event(name="error", level="ERROR", message=str(e))
                raise
            finally:
                tracing.flush()
        return wrapper
    return decorator


def trace_tool(tool_name: str):
    """Decorator to trace tool execution."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracing = get_tracing()
            if not tracing.enabled:
                return func(*args, **kwargs)

            span = tracing.span(trace_id="current", name=f"tool.{tool_name}")
            try:
                result = func(*args, **kwargs)
                span.event(name="tool_result", output=str(result)[:500])
                return result
            except Exception as e:
                span.event(name="tool_error", error=str(e))
                raise
            finally:
                span.end()
        return wrapper
    return decorator


def trace_operation(operation_name: str):
    """Decorator to trace any operation."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracing = get_tracing()
            if not tracing.enabled:
                return func(*args, **kwargs)

            span = tracing.span(trace_id="current", name=operation_name)
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                span.event(name="error", error=str(e))
                raise
            finally:
                span.end()
        return wrapper
    return decorator


@contextmanager
def trace_quality_loop(iteration: int, trace_id: str | None = None):
    """Context manager for tracing quality loop iterations."""
    tracing = get_tracing()
    if not tracing.enabled:
        yield NullSpan()
        return

    span = tracing.span(
        trace_id=trace_id or "current",
        name=f"quality_loop.iteration_{iteration}",
    )
    try:
        yield span
    finally:
        span.end()


def record_quality_score(
    trace_id: str,
    score: Any,
    iteration: int,
):
    """Record quality score to Langfuse."""
    tracing = get_tracing()
    if not tracing.enabled:
        return

    tracing.score(trace_id=trace_id, name="quality.overall", value=score.overall, iteration=iteration)
    tracing.score(trace_id=trace_id, name="quality.factual_accuracy", value=score.factual_accuracy, iteration=iteration)
    tracing.score(trace_id=trace_id, name="quality.source_quality", value=score.source_quality, iteration=iteration)
    tracing.score(trace_id=trace_id, name="quality.logical_coherence", value=score.logical_coherence, iteration=iteration)
    tracing.score(trace_id=trace_id, name="quality.completeness", value=score.completeness, iteration=iteration)
    tracing.score(trace_id=trace_id, name="quality.clarity", value=score.clarity, iteration=iteration)

    if score.hard_gate_failures:
        for failure in score.hard_gate_failures:
            tracing.event(
                trace_id=trace_id,
                name="quality.hard_gate_failure",
                dimension=failure.dimension,
                score=failure.score,
                threshold=failure.threshold,
            )


def record_token_usage(trace_id: str, usage: dict[str, int], model: str):
    """Record token usage."""
    tracing = get_tracing()
    if not tracing.enabled:
        return

    tracing.score(trace_id=trace_id, name="tokens.prompt", value=usage.get("prompt_tokens", 0))
    tracing.score(trace_id=trace_id, name="tokens.completion", value=usage.get("completion_tokens", 0))
    tracing.score(trace_id=trace_id, name="tokens.total", value=usage.get("total_tokens", 0))
    tracing.event(trace_id=trace_id, name="token_usage", model=model, **usage)
