import logging
import sys

from pythonjsonlogger import jsonlogger

from app.core.config import settings


def setup_logging() -> None:
    """Configure application logging system."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stdout)

    if settings.DEBUG:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s"
        )
    else:
        formatter = jsonlogger.JsonFormatter(  # type: ignore[no-untyped-call]
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )

    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
