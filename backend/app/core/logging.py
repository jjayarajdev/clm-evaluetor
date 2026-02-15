"""Structured JSON logging configuration for the application."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# Context variables for request tracking
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)
channel_var: ContextVar[str] = ContextVar("channel", default="system")


def get_request_id() -> str | None:
    """Get the current request ID from context."""
    return request_id_var.get()


def get_user_id() -> str | None:
    """Get the current user ID from context."""
    return user_id_var.get()


def get_session_id() -> str | None:
    """Get the current session ID from context."""
    return session_id_var.get()


def get_channel() -> str:
    """Get the current logging channel from context."""
    return channel_var.get()


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Build the log entry
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request context if available
        request_id = get_request_id()
        if request_id:
            log_entry["request_id"] = request_id

        user_id = get_user_id()
        if user_id:
            log_entry["user_id"] = user_id

        session_id = get_session_id()
        if session_id:
            log_entry["session_id"] = session_id

        # Always include channel
        log_entry["channel"] = get_channel()

        # Add extra fields from the record
        if hasattr(record, "extra_fields") and record.extra_fields:
            log_entry.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add source location for errors and above
        if record.levelno >= logging.ERROR:
            log_entry["location"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            }

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class ContextLogger(logging.LoggerAdapter):
    """Logger adapter that includes context in extra fields."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Process the logging call to add extra context."""
        extra = kwargs.get("extra", {})

        # Add any extra fields passed explicitly
        if "extra_fields" not in extra:
            extra["extra_fields"] = {}

        kwargs["extra"] = extra
        return msg, kwargs

    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info with optional extra fields as kwargs."""
        extra_fields = {k: v for k, v in kwargs.items()
                       if k not in ("exc_info", "stack_info", "stacklevel", "extra")}
        for k in extra_fields:
            kwargs.pop(k)
        if extra_fields:
            kwargs.setdefault("extra", {})["extra_fields"] = extra_fields
        super().info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning with optional extra fields as kwargs."""
        extra_fields = {k: v for k, v in kwargs.items()
                       if k not in ("exc_info", "stack_info", "stacklevel", "extra")}
        for k in extra_fields:
            kwargs.pop(k)
        if extra_fields:
            kwargs.setdefault("extra", {})["extra_fields"] = extra_fields
        super().warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error with optional extra fields as kwargs."""
        extra_fields = {k: v for k, v in kwargs.items()
                       if k not in ("exc_info", "stack_info", "stacklevel", "extra")}
        for k in extra_fields:
            kwargs.pop(k)
        if extra_fields:
            kwargs.setdefault("extra", {})["extra_fields"] = extra_fields
        super().error(msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug with optional extra fields as kwargs."""
        extra_fields = {k: v for k, v in kwargs.items()
                       if k not in ("exc_info", "stack_info", "stacklevel", "extra")}
        for k in extra_fields:
            kwargs.pop(k)
        if extra_fields:
            kwargs.setdefault("extra", {})["extra_fields"] = extra_fields
        super().debug(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical with optional extra fields as kwargs."""
        extra_fields = {k: v for k, v in kwargs.items()
                       if k not in ("exc_info", "stack_info", "stacklevel", "extra")}
        for k in extra_fields:
            kwargs.pop(k)
        if extra_fields:
            kwargs.setdefault("extra", {})["extra_fields"] = extra_fields
        super().critical(msg, *args, **kwargs)


def get_logger(name: str) -> ContextLogger:
    """Get a context-aware logger instance.

    Args:
        name: Logger name (typically __name__).

    Returns:
        ContextLogger instance with JSON formatting.
    """
    logger = logging.getLogger(name)
    return ContextLogger(logger, {})


def configure_logging(log_level: str = "INFO", json_output: bool = True) -> None:
    """Configure application-wide logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_output: Whether to use JSON format (True) or plain text (False).
    """
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if json_output:
        console_handler.setFormatter(JSONFormatter())
    else:
        # Plain text format for development
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(console_handler)

    # Configure specific loggers
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Log startup message
    startup_logger = get_logger("app.core.logging")
    startup_logger.info(
        f"Logging configured: level={log_level}, json={json_output}",
        log_level=log_level,
        json_output=json_output,
    )
