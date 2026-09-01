from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime
from typing import Any

logger = logging.getLogger("prava")

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def configure_logging(level: str = "INFO") -> None:
    """Readable, timestamped app logs to stdout so Railway can display them. Idempotent."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    app_logger = logging.getLogger("prava")
    app_logger.handlers = [handler]
    app_logger.setLevel(level)
    app_logger.propagate = False


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def log_event(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **fields}, default=_json_default, sort_keys=True))


def log_exception(event: str, exc: BaseException, **fields: Any) -> None:
    logger.error(
        json.dumps(
            {"event": event, "error": exc.__class__.__name__, **fields},
            default=_json_default,
            sort_keys=True,
        ),
        exc_info=exc,
    )
