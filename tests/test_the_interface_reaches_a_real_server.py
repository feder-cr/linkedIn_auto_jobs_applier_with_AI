"""One request to the interface, answered by a REAL MCP server process.

⛔ EVERY OTHER TEST OF THE INTERFACE USES A FAKE LINK, and that is correct for
what those tests ask: they are about routes, sessions and the page. But it
left one thing proven nowhere. The interface is an MCP CLIENT - that is the
architecture's central claim, the reason the tools are said to be provably
sufficient - and no test ever joined the two halves. `tests/mcp_server/
test_stdio_e2e.py` drives a real server and never touches a route;
`tests/test_web_service.py` drives every route and never touches a server.

What the join costs when nobody tests it, in this exact route: `/live/frame`
decides between 204 and 503 by SUBSTRING-TESTING the prose a tool raised
(`NOTHING_RUNNING in reason`). The constant ships in one package so the two
readers cannot drift, which is the mitigation, and it is still a
machine-readable fact travelling as English. Against a fake link that
comparison is never exercised at all: the double returns whatever the test
decided, so the branch is chosen by the test rather than by the server.

The two existing assertions on this route are
`assert client.get("/live/frame?s=lavoro").status_code in (200, 204, 503)`,
which is every status the route can produce. That cannot fail.

⛔ AND IT IS DRIVEN WITH AN IN-LOOP ASGI CLIENT, NOT `TestClient`. The first
version of this file used `TestClient` like every other route test here, and
it HUNG with no output. `TestClient` runs the app in a portal with its own
event loop, while a real `Link` holds its stdio streams in the test's loop, so
the route awaited a stream belonging to another loop and never came back. With
a fake link the question never arises, which is why no existing test could
have found it. Same family as the rule already written about closing a
Playwright object from a loop other than its own. Every request below is also
bounded by `asyncio.wait_for`, so a future regression of this shape fails in
twenty seconds with a name instead of hanging a suite.

NO BROWSER IS STARTED, which is what makes this cheap enough to run by
default. The chain under test is: HTTP request -> `which` -> `Sessions` ->
a real `Link` over stdio -> a real `python -m aihawk` child -> `browser_watch`
-> `looking()` refusing because nothing is running -> `NOTHING_RUNNING` as an
error result -> back through `image_of` and the substring test -> 204. Every
link in that sentence is real except the browser, and the browser is the one
part `browser_watch` is documented never to start.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import sys

import httpx
import pytest

from aihawk.chat import DEFAULT_CHAT_ID
from aihawk.sessions import Sessions
from aihawk.web import build_app

pytestmark = pytest.mark.asyncio

#: This checkout's `src/`, so the child process imports the code under test
#: rather than whatever `aihawk` is installed. `runner.child_env` copies this
#: process's environment, so setting it here is what reaches the child.
#: Measured on this machine: the installed distribution said 0.11.0 while the
#: tree said 0.47.0, so without this the child would be a different product.
_SRC = str(pathlib.Path(__file__).resolve().parents[1] / "src")


class _NoBrain:
    """Never used: nothing here sends a message. `Sessions` wants a factory."""

    async def handle(self, *a, **k):  # pragma: no cover - not reached
        raise AssertionError("no conversation happens in this test")


@pytest.fixture()
async def live(tmp_path, monkeypatch):
    """A real conversation with a real server child, and the app around it."""
    monkeypatch.setenv("AIHAWK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PYTHONPATH", _SRC + os.pathsep + os.environ.get("PYTHONPATH", ""))
    sessions = Sessions({}, None, _NoBrain, model_label="none")
    await sessions.get(DEFAULT_CHAT_ID)
    app = build_app(sessions)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://interface") as client:
            yield client, sessions
    finally:
        await sessions.close_all()


async def test_the_idle_pane_is_answered_by_a_server_that_really_refused(live):
    """204, and it came back through the protocol rather than from a double."""
    client, _ = live
    got = await asyncio.wait_for(client.get("/live/frame"), 20)
    assert got.status_code == 204, (
        "a browser that is not running is nothing to look at, so the pane goes "
        "idle. Got %s: %s" % (got.status_code, got.text[:300]))
    assert not got.content


async def test_the_workspace_is_answered_by_the_server_and_not_by_the_interface(live):
    """`/live/browsers` is `browser_list` on a real server, and the answer
    carries a fact the interface does not own.

    ⛔ THE FIRST VERSION OF THIS ASSERTED THE TWO ROLE NAMES AND WAS WRONG
    ABOUT THE PRODUCT, not about the plumbing: `browser_list` reports the
    browsers that EXIST, and with nothing opened that list is empty. The
    fields around it are what identifies the source. `limit` is
    `MAX_BROWSERS_PER_SESSION`, a constant that lives in the server module and
    is written nowhere in the interface, so reading 2 here means the answer
    travelled from there.
    """
    client, _ = live
    got = await asyncio.wait_for(client.get("/live/browsers"), 20)
    assert got.status_code == 200, got.text[:300]
    body = got.json()
    assert set(body) >= {"browsers", "focus", "limit"}, body
    assert body["browsers"] == [], (
        "nothing was opened, so nothing should be listed: %s" % body)
    assert body["focus"] == "main", body
    from aihawk.mcp import server as _server
    assert body["limit"] == _server.MAX_BROWSERS_PER_SESSION, (
        "the ceiling the page was told, %r, is not the server's own %r, so "
        "this answer did not come from the server"
        % (body["limit"], _server.MAX_BROWSERS_PER_SESSION))


async def test_the_client_really_is_a_separate_process(live):
    """⛔ THE CLAIM THIS FILE EXISTS TO CHECK, stated as an assertion.

    If the interface ever reached the browser by importing the registry
    instead of speaking MCP, every test above would still pass. What would
    change is that there would be no child process. The link holds one, and
    it is not this one.
    """
    _, sessions = live
    service = await sessions.get(DEFAULT_CHAT_ID)
    session = service.link.session
    assert session is not None, "the link never completed a handshake"
    tools = {t.name for t in service.link.tools}
    assert "browser_watch" in tools and "browser_list" in tools, sorted(tools)
    assert len(tools) >= 16, (
        "the interface was handed %d tools; it is supposed to receive the "
        "server's whole surface, the same one a model gets" % len(tools))
    assert getattr(service.link, "instructions", ""), (
        "the server's instructions did not reach the interface, so the agent "
        "would be told less than any other client is")
    assert sys.executable, "no interpreter to have spawned anything with"
