from __future__ import annotations

import sqlite3
from pathlib import Path


def open_connection(db_path: Path) -> sqlite3.Connection:
    """Open a sqlite3 connection with sqlite-vec loaded.

    Raises RuntimeError with an actionable message if the Python interpreter
    was built without SQLite loadable-extension support (common on macOS system
    Python). Lets callers render a health-check failure rather than crash.
    """
    import sqlite_vec

    # check_same_thread=False: MCP tool dispatch may call query/add from a
    # thread other than the one that opened this connection. Writes are
    # serialized inside `with con:` blocks; reads are SQLite-thread-safe.
    con = sqlite3.connect(db_path, check_same_thread=False)
    if not hasattr(con, "enable_load_extension"):
        raise RuntimeError(
            "sqlite3 has no enable_load_extension; this Python was built without "
            "SQLite loadable-extension support. Install via Homebrew python@3.13 "
            "or rebuild pyenv with PYTHON_CONFIGURE_OPTS="
            "'--enable-loadable-sqlite-extensions'."
        )
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    return con
