from __future__ import annotations

import re
from typing import Any

_REDACTION_PLACEHOLDER = "***"

_SENSITIVE_KEY_RE = re.compile(
    r"""
    ^(
        api[_-]?key | apikey |
        secret[_-]?key | secret |
        auth[_-]?token | token | bearer |
        password | passwd |
        private[_-]?key |
        access[_-]?key | access[_-]?token |
        refresh[_-]?token
    )$
    | _(api[_-]?key|apikey|secret|token|password|passwd|bearer|access[_-]?key)$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def is_sensitive_key(key: str) -> bool:
    """True if a config/log key should have its value redacted in human output.

    Matches exact names (`api_key`, `token`, `password`, ...) and suffix patterns
    (`github_token`, `stripe_api_key`) — but NOT incidental substrings like
    `secret_path` or `keystore_dir`.
    """
    return bool(_SENSITIVE_KEY_RE.search(key))


def redact_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of `config` with sensitive string values replaced."""
    out: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, str) and is_sensitive_key(key):
            out[key] = _REDACTION_PLACEHOLDER
        else:
            out[key] = value
    return out
