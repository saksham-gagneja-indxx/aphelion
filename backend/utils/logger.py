"""
Centralized logging configuration for Social Media Automation Agent
Handles both file and console logging with appropriate levels
"""

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from backend.utils.config import get_settings


def _reconfigure_stream_to_utf8(stream):
    """Force a std stream to UTF-8 if it supports reconfiguration.

    Windows consoles default to cp1252, which cannot encode the emoji used in
    this codebase's log messages. Silently ignored where unsupported (e.g. when
    the stream has been replaced by a non-TextIO object under a test harness).
    """
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def setup_logging():
    """Configure logging for the application"""
    settings = get_settings()

    # Create logs directory if it doesn't exist
    log_dir = Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger("social_media_automation")
    logger.setLevel(getattr(logging, settings.log_level))

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatters
    formatter = logging.Formatter(settings.log_format)

    # File handler (rotating).
    # encoding is explicit: log messages across this codebase contain emoji,
    # and on Windows the default (cp1252) raises UnicodeEncodeError on them.
    file_handler = logging.handlers.RotatingFileHandler(
        settings.log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, settings.log_level))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler. Same reason: force the stream to UTF-8 so a Windows
    # cp1252 console doesn't crash the logger on emoji.
    _reconfigure_stream_to_utf8(sys.stdout)
    _reconfigure_stream_to_utf8(sys.stderr)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str = "social_media_automation"):
    """Get a logger instance for a specific module"""
    return logging.getLogger(name)


# Module-specific loggers
agent_logger = get_logger("social_media_automation.agent")
scheduler_logger = get_logger("social_media_automation.scheduler")
api_logger = get_logger("social_media_automation.api")
database_logger = get_logger("social_media_automation.database")
ai_logger = get_logger("social_media_automation.ai")
instagram_logger = get_logger("social_media_automation.instagram")
linkedin_logger = get_logger("social_media_automation.linkedin")


class LoggerContext:
    """Context manager for structured logging"""

    def __init__(self, logger: logging.Logger, action: str):
        self.logger = logger
        self.action = action

    def __enter__(self):
        self.logger.info(f"▶️  Starting: {self.action}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.logger.info(f"✅ Completed: {self.action}")
        else:
            self.logger.error(
                f"❌ Failed: {self.action}",
                exc_info=(exc_type, exc_val, exc_tb)
            )
        return False


def log_action(logger: logging.Logger, action: str):
    """Decorator for logging function execution"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with LoggerContext(logger, f"{func.__name__}: {action}"):
                return func(*args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    logger = setup_logging()
    logger.info("🚀 Logging system initialized")
    logger.debug("Debug message example")
    logger.warning("Warning message example")
    logger.error("Error message example (non-fatal)")
    print(f"✅ Logs are being written to: {get_settings().log_file}")
