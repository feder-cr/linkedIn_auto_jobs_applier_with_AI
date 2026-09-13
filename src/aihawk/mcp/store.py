"""What a session is, written down so it survives the process.

A session is the piece of work: it owns browsers, and each browser owns tabs.
Until this file existed all three lived in dictionaries that died with the
server, so "reopen the session I was working in" meant nothing.

⛔ WHAT IS PROMISED, AND WHAT IS NOT. What is saved is the DECLARATION: which
browsers a session has, who each one is (seed, exit, profile), which one had the
focus, and where its tabs were pointing. Reopening restores that declaration -
not eight live browsers. Eight of those were measured at 61 processes and about
6.5 GB, with the eighth taking 13.6 s to start, so a reopen that launched them
all would take a minute and most of the machine's memory to give back something
nobody asked for yet. They start when a command is aimed at one, as the right
person, because the identity was written down.

Cookies and logins survive only where a browser had a `profile` directory, which
is the mechanism that already exists for exactly that. Saying otherwise would be
promising that a browser's live state is a thing this file can hold, and it is
not.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from ..storage import (DEFAULT_SESSION_ID, home, safe_name as _safe,
                       write_atomically)


#: The piece of work a caller that names none is in, and so the file it
#: persists to.
#:
#: ⛔ ONE DECLARATION, BECAUSE TWO OF THEM CANNOT BE HELD TOGETHER BY A TEST
#: THAT COMPARES ONE OF THEM TO A LITERAL. This lived in `registry.py` as
#: `DEFAULT_SESSION_ID` while `chat.py` declared `DEFAULT_CHAT_ID = "default"`
#: beside it, with a comment saying the two had to match. What guarded that was
#: an assertion reading `DEFAULT_CHAT_ID == "default"` - a literal, not the
#: other constant - so moving the server's default would have left the
#: interface and the server addressing two different files while the test that
#: names the invariant stayed green.
#:
#: It belongs here rather than in the registry: the registry keys BROWSERS, and
#: this names a piece of WORK, which is to say a file in this directory. The
#: registry never needed it except as a default argument no caller used.
#: Re-exported: the constant itself lives in `aihawk.storage`, because the
#: interface's half needs the same value and a second literal is how the two
#: halves would quietly start naming different pieces of work.
_ = DEFAULT_SESSION_ID  # re-exported for callers that import it from here


def _sessions_dir() -> Path:
    return home() / "sessions"


def path_of(session_id: str) -> Path:
    return _sessions_dir() / ("%s.json" % _safe(session_id))


def save(session_id: str, browsers: Dict[str, dict],
         focus: Optional[str] = None) -> Path:
    """Write one session down. Returns where it went.

    ⛔ `write_bytes`, never `write_text`. On Windows the text form translates
    every newline on the way out, which in this project has already turned a
    twenty-line change into a fifteen-thousand-line one. JSON does not care, but
    the habit is what keeps the next file that does care safe.

    Written to a temporary neighbour and moved into place, so a process that
    dies mid-write leaves the previous session intact rather than half of a new
    one. A session file that will not parse is worse than an old one.
    """
    where = path_of(session_id)
    payload = {
        "id": session_id,
        # Inert, and kept anyway: nothing has read it since `session_list` was
        # removed, and no caller ever passed a name, so it has always equalled
        # `id`. Dropping it would change the bytes of every saved file to
        # delete a line, which is not a trade worth making for a field that
        # costs nothing and that an older build rolled back onto this directory
        # would still expect to find.
        "name": session_id,
        "saved": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "focus": focus,
        "browsers": browsers,
    }
    blob = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    write_atomically(where, blob)
    return where


def load(session_id: str) -> Optional[dict]:
    """One session as it was written, or None if there is nothing to read.

    A file that will not parse answers None as well. The alternative is raising
    on a server's first call because something once wrote a broken byte, and a
    session that cannot be read is exactly as usable as one that was never
    saved.
    """
    where = path_of(session_id)
    try:
        return json.loads(where.read_bytes().decode("utf-8"))
    except Exception:
        return None


# ⛔ `known()` STOOD HERE, listing every saved session newest first. Its only
# caller was the `session_list` tool, and that tool was removed when MCP
# stopped having a session concept: enumerating pieces of work other than this
# process's own is precisely the capability that went. Nothing else ever
# globbed this directory - the interface lists CONVERSATIONS, through
# `known_chats` below.


def erase(session_id: str) -> bool:
    """Forget a saved session. Answers whether there was one."""
    where = path_of(session_id)
    try:
        where.unlink()
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False
