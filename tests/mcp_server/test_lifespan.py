"""The lifespan must NOT close the sessions, and that is the whole point.

FastMCP runs the lifespan per MCP session, which is per CLIENT rather than once
per process. Measured while building this: with one client attached the machine
had 7 firefox processes, and a second after that client disconnected it had 1
again, because the lifespan was closing the registry. A browser that dies when
somebody detaches cannot be shared, cannot outlive a chat, and cannot back a
live view.

So these tests assert the absence of a behaviour. They fail against any version
that cleans up here, including the one this replaced.
"""
import pytest

#: The browser this file addresses. Explicit since the registry's key
#: stopped having a default: a bare "default" was never a key any browser
#: occupied, because the server composes `<piece of work>/<browser>`.
KEY = "default/main"


class _FakeSession:
    def __init__(self, **kwargs):
        self.closed = False
        self._browser = None
        self._context = object()

    async def start(self):
        pass

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_a_client_leaving_does_not_close_its_browser():
    from aihawk.mcp import server

    fake = _FakeSession()
    server.work.registry._browsers[KEY] = fake

    async with server._lifespan(server.mcp) as ctx:
        assert ctx == {}

    assert fake.closed is False, "the lifespan closed a session; a second client would find no browser"
    assert server.work.registry.peek(KEY) is fake

    await server.work.registry.close_all()


@pytest.mark.asyncio
async def test_several_clients_coming_and_going_leave_every_session_alone():
    from aihawk.mcp import server

    a, b = _FakeSession(), _FakeSession()
    server.work.registry._browsers["chat"] = a
    server.work.registry._browsers["someone-else"] = b

    for _ in range(3):
        async with server._lifespan(server.mcp):
            pass

    assert a.closed is False and b.closed is False
    assert server.work.registry.ids() == ["chat", "someone-else"]

    await server.work.registry.close_all()


@pytest.mark.asyncio
async def test_close_all_is_what_actually_shuts_them_down():
    """The cleanup did not disappear, it moved. It runs when the PROCESS ends,
    which on stdio is the same moment a client leaves, so nothing changes for
    the clients that exist today."""
    from aihawk.mcp import server

    fake = _FakeSession()
    server.work.registry._browsers[KEY] = fake

    await server.work.registry.close_all()

    assert fake.closed is True
    assert server.work.registry.ids() == []


def _main_with(monkeypatch, transport):
    """Run `main()` under this transport with the serving and the hook stubbed,
    and answer what it registered with atexit."""
    import atexit

    from aihawk.mcp import server

    registered = []
    monkeypatch.setattr(atexit, "register", lambda fn, *a, **k: registered.append(fn))
    monkeypatch.setattr(server.mcp, "run", lambda *a, **k: None)
    monkeypatch.setattr(server, "_close_on_lifespan_exit", False)
    if transport is None:
        monkeypatch.delenv("STEALTHFOX_MCP_TRANSPORT", raising=False)
    else:
        monkeypatch.setenv("STEALTHFOX_MCP_TRANSPORT", transport)
    server.main()
    return registered


def test_over_http_the_exit_hook_is_registered(monkeypatch):
    """Without this the browsers would simply leak over HTTP: the lifespan
    there is per CLIENT and must not close anything, so process exit is the
    only moment left, and Firefox is a tree of processes holding a profile
    directory and a port.

    ⛔ BEHAVIOUR, NOT A SCAN. This used to walk the module's AST for a
    top-level `atexit.register(...)` line, because `atexit` exposes no way to
    read what is registered. Stubbing `atexit.register` for the span of one
    `main()` call reads exactly that, and it can tell the two transports
    apart, which a scan for a module-level line never could.

    Known-bad: drop the `atexit.register` line from the HTTP branch of
    `main()`. Green before; red now.
    """
    from aihawk.mcp import server

    registered = _main_with(monkeypatch, "http")

    assert server._close_sessions_at_exit in registered, (
        "over HTTP nothing registers the browser-closing hook, so an ending "
        "process leaves Firefox holding its profile directory and its port")
    assert server._close_on_lifespan_exit is False, (
        "the HTTP lifespan is per client and must not close the browsers")


def test_over_stdio_the_lifespan_closes_and_no_hook_is_registered(monkeypatch):
    """Over stdio the lifespan exit IS the last moment the loop that opened
    the browsers still runs, so the close happens there. An atexit hook on top
    would run in a NEW loop, where an await on a Playwright object from the
    finished one never answers - measured at 180 s of waiting on Linux.

    Known-bad: register the hook unconditionally at import, as this module
    did until this test existed. Green before; red now.
    """
    from aihawk.mcp import server

    registered = _main_with(monkeypatch, None)

    assert server._close_on_lifespan_exit is True
    assert server._close_sessions_at_exit not in registered, (
        "stdio registered the exit hook as well, which runs in a loop that is "
        "not the browsers' own and hangs the process on exit")
