"""A silence with its reason written where the silence is.

Some failures are rightly swallowed: a full disk must not turn a finished turn
into an error, a page that is already gone cannot be closed twice. Until 0.52.0
each of those was `except Exception: pass` with the reason in a comment beside
it - thirteen of them - and a comment is the one thing a reader can skip and a
gate cannot see. `swallow(why)` makes the reason an argument: it is on the
line that swallows, it is greppable, and it is LOGGED at debug with the
traceback, so a silence that hides a real defect can be heard by turning the
logger up instead of by adding a print.

The workbench records what an unheard silence cost: a live pane frozen on an
old page for a whole session, because the capture had stopped and the only
sign was a swallowed exception nobody could see ([B202]).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

log = logging.getLogger("aihawk")


@contextmanager
def swallow(why: str) -> Iterator[None]:
    """Run the block and let any exception go, for this stated reason."""
    try:
        yield
    except Exception:
        log.debug("swallowed: %s", why, exc_info=True)
