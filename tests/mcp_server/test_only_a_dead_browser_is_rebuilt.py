"""A page that refuses keeps the browser it refused on. Only a browser that is
GONE is rebuilt.

⛔ UNTIL 0.50.0 EVERY FAILURE WAS A DEAD BROWSER. `_retrying` caught
`Exception`, closed the healthy browser, started a new one as the same person,
reopened its last page and ran the action again. A domain that does not
resolve fails identically the second time, so the caller got the same error a
browser later - minus the cookies, the logins and the pages the first one
held. Measured 2026-09-14 on the interface: `NS_ERROR_UNKNOWN_HOST` on the
second command of a conversation, and the person watched the `main` window
close and reopen for a typo.

No browser starts here. The registry takes a factory whose sessions record
whether they were closed, so the whole behaviour is observable from which
object the action ran on.

Known-bad, run before this file was trusted: `except Exception:` with no
question asked, as it was - the first two tests go red. And `is_dead` reading
only the type, without `_is_usable` - the last one goes red.
"""
from __future__ import annotations

import pytest

from aihawk.mcp import server
from aihawk.mcp.work import Work
from invisible_playwright.async_api import TargetClosedError


class _Session:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._browser = None
        self._context = object()
        self.closed = False

    async def start(self):
        pass

    async def close(self):
        self.closed = True

    def where_pages_are(self):
        return []


@pytest.fixture
def registry(monkeypatch):
    w = Work("default", factory=_Session,
                              defaults=lambda: {"seed": 7, "headless": True})
    monkeypatch.setattr(server, "work", w)
    reg = w.registry
    return reg


async def test_a_page_that_refuses_does_not_cost_the_browser(registry):
    async def refuses(session):
        raise RuntimeError("Page.goto: NS_ERROR_UNKNOWN_HOST")

    before = await server.work.ready()
    with pytest.raises(RuntimeError, match="UNKNOWN_HOST"):
        await server.work.retrying(refuses)

    assert not before.closed, "a healthy browser was closed over a page's refusal"
    assert registry.peek(server.work.key()) is before, (
        "the browser was replaced over a page's refusal")


async def test_a_refusal_is_reported_once_not_tried_twice(registry):
    """The retry is for a browser that came back; there is nothing to retry on
    a browser that never left."""
    calls = []

    async def refuses(session):
        calls.append(session)
        raise RuntimeError("Page.goto: Timeout 45000ms exceeded")

    await server.work.ready()
    with pytest.raises(RuntimeError, match="Timeout"):
        await server.work.retrying(refuses)

    assert len(calls) == 1, "the failed navigation was run again"


async def test_a_browser_that_is_gone_is_rebuilt_as_the_same_person(registry):
    """The recovery this function exists for, kept: the TYPE a closed target
    raises - one class since invisible-playwright 0.15.0, for a disposed
    object and a closed pipe alike - is a browser that is gone, and the action
    is run again on a replacement with the same identity."""
    calls = []

    async def gone_then_fine(session):
        calls.append(session)
        if len(calls) == 1:
            raise TargetClosedError("Target page, context or browser has been closed")
        return "done"

    before = await server.work.ready()
    got, rebuilt = await server.work.retrying(gone_then_fine)

    assert got == "done"
    assert rebuilt, "the rebuild happened and the answer did not say so"
    assert before.closed, "the dead browser was not discarded"
    assert calls[1] is not before, "the action was retried on the dead browser"
    assert calls[1].kwargs.get("seed") == before.kwargs.get("seed"), (
        "the replacement is somebody else")


async def test_a_browser_that_reports_itself_dead_is_rebuilt_whatever_it_said(registry):
    """The other witness: a session whose connection dropped answers `_is_usable`
    with no, and the wording of the failure that surfaced is beside the point."""
    calls = []

    async def dies(session):
        calls.append(session)
        if len(calls) == 1:
            session._context = None      # what a dead browser looks like from here
            raise RuntimeError("something the page said on its way down")
        return "done"

    before = await server.work.ready()
    assert await server.work.retrying(dies) == ("done", True)
    assert calls[1] is not before, "a browser that reported itself dead was kept"
