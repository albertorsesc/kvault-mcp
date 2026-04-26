from __future__ import annotations

import re

_STRIP_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


def sanitize_fts_query(query: str) -> str:
    """Escape user input into a safe FTS5 phrase query.

    FTS5 treats unquoted punctuation as operators. Strip everything but word-chars
    and whitespace, then wrap each token in double quotes so every term is a
    literal phrase match. Empty input resolves to the empty phrase `""`.
    """
    cleaned = _STRIP_NON_WORD.sub(" ", query).strip()
    if not cleaned:
        return '""'
    return " ".join(f'"{tok}"' for tok in cleaned.split())
