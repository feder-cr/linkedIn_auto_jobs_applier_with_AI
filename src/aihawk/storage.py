"""The three things both halves of a session need to write themselves down.

A session is kept in two files by two programs: the browsers by the MCP
server (`aihawk.mcp.store`) and the conversation by the interface
(`aihawk.chats`). They must agree about WHERE the data lives and about HOW an
id becomes a file name, or the join between them breaks; and they must both
replace a file without ever leaving a half-written one behind.

⛔ THOSE THREE THINGS WERE WRITTEN TWICE. `home()` and the id sanitiser lived
in the server's module and the interface reached into it to borrow them, which
is how the interface's persistence came to live inside the MCP package at all.
The atomic write was copied outright: four lines, in both files, with only one
of the two carrying the comment explaining why it has to be `write_bytes`.
Two copies of one rule is the arrangement where a fix reaches one of them.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

#: The id of the session a process serves when nobody names one.
#:
#: It lives here rather than in either half because both halves need it to
#: mean the same thing: the interface's default conversation and the server's
#: default browser file are the same piece of work, and a second literal is
#: how they would quietly become two.
DEFAULT_SESSION_ID = "default"


def home() -> Path:
    """Where sessions are kept.

    `AIHAWK_HOME` wins, which is what the tests use and what lets somebody put
    this on another disk. Otherwise the place each system expects, so a person
    finds it where they would look for it rather than in a dotfile invented
    here.
    """
    override = os.environ.get("AIHAWK_HOME")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(base) / "aihawk"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "aihawk"
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "aihawk"


def safe_name(session_id: str) -> str:
    """A session id as a file name, without letting one escape the directory.

    A caller could send `../../etc` or a colon that Windows refuses. Anything
    outside the allowed set becomes an underscore rather than being rejected: a
    session should not become unreachable because of the name somebody gave it.
    """
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    cleaned = "".join(c if c in allowed else "_" for c in session_id)
    return cleaned[:120] or "_"


def write_atomically(where: Path, blob: bytes) -> None:
    """Replace a file with these bytes, or leave the old one untouched.

    Written beside the target and moved onto it, because the reader is another
    program: a plain write that is interrupted, or read while it is happening,
    hands somebody half a JSON document and loses what was there.

    ⛔ `write_bytes`, never `write_text`. On Windows the text form translates
    every newline on the way out, so a file written here and compared
    elsewhere differs by bytes nobody wrote.
    """
    where.parent.mkdir(parents=True, exist_ok=True)
    beside = where.with_suffix(where.suffix + ".writing")
    beside.write_bytes(blob)
    os.replace(beside, where)
