from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_ROOT_NAME = "kvault"
_CONFIGURED = False
_CUSTOM_FIELDS = ("plugin_id", "event", "tool_id", "count")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")
        payload: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for attr in _CUSTOM_FIELDS:
            val = getattr(record, attr, None)
            if val is not None:
                payload[attr] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def _configure_root(level: str = "info") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    root = logging.getLogger(_ROOT_NAME)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def make_logger(plugin_id: str, level: str = "info") -> logging.Logger:
    _configure_root(level=level)
    logger = logging.getLogger(f"{_ROOT_NAME}.{plugin_id}")
    # merge_extra=True so per-call extra={"count": ...} isn't clobbered by the
    # adapter's {"plugin_id": ...} (default LoggerAdapter behavior is REPLACE).
    return logging.LoggerAdapter(logger, {"plugin_id": plugin_id}, merge_extra=True)  # type: ignore[return-value]
