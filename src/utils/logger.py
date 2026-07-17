"""
Structured logging with structlog.
"""
from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from typing import Any, TextIO

import structlog
from structlog.types import EventDict, Processor

from src.config import get_settings


def add_service_info(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add service information to log entries."""
    event_dict["service"] = "multi-agent-research-lab"
    event_dict["version"] = "0.1.0"
    return event_dict


def add_trace_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add trace context if available."""
    try:
        from langfuse import get_current_trace_id
        trace_id = get_current_trace_id()
        if trace_id:
            event_dict["trace_id"] = trace_id
    except Exception:
        pass
    return event_dict


def configure_logging(
    level: str = "INFO",
    format: str = "json",
    log_file: str | None = None,
    stream: TextIO | None = None,
):
    """Configure structured logging."""
    settings = get_settings()
    output_stream = stream or sys.stdout

    # Reset handlers so basicConfig works on repeated calls
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    logging.basicConfig(
        format="%(message)s",
        stream=output_stream,
        level=getattr(logging, level.upper(), logging.INFO),
        force=True,
    )

    # Configure structlog processors
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_service_info,
        add_trace_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.reset_defaults()
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(file_handler)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class LogContext:
    """Context manager for adding structured context to logs."""

    def __init__(self, **kwargs: Any):
        self.kwargs = kwargs
        self.bound_logger = None

    def __enter__(self) -> structlog.stdlib.BoundLogger:
        self.bound_logger = structlog.get_logger().bind(**self.kwargs)
        return self.bound_logger

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.bound_logger:
            self.bound_logger = None


@contextmanager
def bind_context(**kwargs: Any):
    """Context manager to bind context variables."""
    structlog.contextvars.bind_contextvars(**kwargs)
    try:
        yield
    finally:
        for key in kwargs:
            structlog.contextvars.unbind_contextvars(key)
