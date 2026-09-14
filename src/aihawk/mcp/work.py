"""One piece of work: the two browsers this process serves, where each one
was, and the file it is all written down in.

⛔ AN OBJECT, WHERE THIS WAS FOUR MODULE GLOBALS AND A DOZEN FUNCTIONS READING
THEM. `registry`, `_restored`, `_seen_tabs` and `_tabs_owed` sat at the top of
`server.py`, and every fixture that wanted a clean server rebuilt all four by
hand - the tell of state that wants to be one thing with one lifecycle. The
cost showed on 2026-09-14, three times in one afternoon: the session file
carried a launch flag because "what this process decides" and "who a browser
is" had no place to be different in; a rebuild on ANY failure was a bare
`except` in a free function, and nobody noticed a healthy browser being thrown
away over a domain that did not resolve; and the rebuild itself was silent,
so a person watching the window saw it close and reopen with no word about it
in the transcript. The workbench records them as [B202], [B203] and [B204].

The lifecycle, in the order it happens:

  declare   `restore()` reads the saved file and declares who `main` is,
            without starting anything.
  wake      `ready()` starts a declared browser the first time a COMMAND is
            aimed at it, and reopens the one page the file owed it.
  look      `looking()` and `already_open()` answer a browser that is running
            and never start one: a question is not a command.
  act       `retrying()` runs one action, and rebuilds the browser once - as
            the same person, back on its page - only if the browser is GONE.
  remember  `remember()` writes down who is held and where, on every change
            of identity and every move of a page.
  close     `close_all()` at the end of the process.

There is exactly one of these per process, because a process serves exactly
one piece of work; `server.py` builds it from `AIHAWK_SESSION_ID` and every
tool goes through it. A test builds its own with a factory that launches no
browser and installs it in the server's place: one object, not four globals.
"""
from __future__ import annotations

from typing import Awaitable, Callable, Optional

from . import actions, plan, store
from .registry import BrowserRegistry
from .session import StealthSession

#: The browser a caller means when it names nothing.
DEFAULT_BROWSER_ID = "main"

#: The other one. See MAX_BROWSERS_PER_SESSION for why there are exactly two.
SUPPORT_BROWSER_ID = "support"

#: TWO browsers in one piece of work, with fixed roles, and the number is a
#: decision rather than a measurement - the opposite of what it was until
#: 2026-09-11.
#:
#: It used to be eight, and the eight was measured: 61 processes and 6,515 MB,
#: the eighth taking 13.6 s to start against the first one's 6.8. Nothing about
#: that stopped being true. What changed is what a session MEANS. Identity lives
#: on the browser - seed, fingerprint, profile - so a session holding eight
#: browsers held eight identities while everything above it, the transcript and
#: the saved state and anything a person attaches to a session, was addressed
#: to one. "Whose is this?" had two possible answers and no way to choose.
#:
#: So a session is ONE identity, `main`, plus ONE helper beside it, `support`,
#: for the things that must not touch that identity: a temporary mailbox to
#: receive a verification, a lookup, a second opinion on a page. It is a
#: browser and not a tab because a tab would share cookies and fingerprint with
#: the site the identity is being built on, and the whole point of the helper
#: is that it does not. The helper is not saved and not restored - it dies with
#: the process - because a helper that survives IS a second identity, which is
#: the thing this number exists to rule out.
#:
#: The roles are NAMES A CALLER CANNOT INVENT. `browser` on every tool is a
#: closed choice, `main` or `support`, so nothing here ever holds a browser
#: called `b3` or `walmart-jobs` again. The design that went with the eight is
#: in the workbench, under
#: `docs_research/chat-ui-performance/30-PROGETTO-sessioni-e-otto-browser.md`.
MAX_BROWSERS_PER_SESSION = 2

#: The launch settings that say WHO a browser is, and so the ones a saved file
#: carries. Everything else in the launch kwargs describes THIS LAUNCH - the
#: engine it runs on, whether its window is shown - and is decided by
#: `plan.launched_here` every time, never read back from a file. Both halves
#: of that were measured by getting them wrong: `binary_path` saved would
#: restore a browser onto a path that means nothing on another machine, and
#: `headless` saved (until 0.50.0) made one headed run decide for every later
#: process that read the same file.
#:
#: ⛔ THESE ARE THE LAUNCH KWARGS' OWN NAMES, NOT THE TOOL ARGUMENTS' NAMES:
#: this list said `profile` for its first day, the launch kwarg is
#: `profile_dir`, so the filter matched nothing and the profile - the one
#: field that carries the logins a reopened browser is FOR - was never saved.
WHO_A_BROWSER_IS = ("seed", "proxy", "profile_dir")

#: What a READ says when nothing is running.
#:
#: ⛔ NOT `NOTHING_RUNNING`, WHICH IS THE WATCH PANE'S SENTENCE. That one ends
#: "any command aimed at one starts it", which stays true of a command and is
#: exactly what stopped being true of a look. Reusing it would tell a model to
#: retry the read it just made, which is the one thing that cannot work now.
NOTHING_TO_READ = ("no browser is running in %r, so there is nothing to read. "
                   "Open one with browser_open, or send a command such as "
                   "browser_navigate, which starts it. Reading does not.")

#: What the listing says when nothing is open. Same rule as the read's
#: sentence, said of the whole piece of work: a command opens a browser, a
#: read does not, and the listing is a read.
NO_BROWSER_OPEN = ("no browser open yet. Open one with browser_open, or send a "
                   "command such as browser_navigate, which starts it. Listing "
                   "does not.")

#: What an action's answer is prefixed with when the browser had to be rebuilt
#: underneath it. Said, because until 0.51.0 it was not: a person watching the
#: window saw it close and reopen, and the transcript showed a navigation that
#: simply worked. A model reading this knows the cookies of an ephemeral
#: browser are gone and a login may need redoing.
REBUILT = ("the %s browser had died and was reopened as the same person, on "
           "the page it was on; then: ")


class Work:
    """The one piece of work this process serves. See the module docstring
    for the lifecycle; every method here is one step of it."""

    def __init__(self, session_id: str, *, factory=StealthSession,
                 defaults: Optional[Callable[[], dict]] = None) -> None:
        self.session_id = session_id
        #: The browsers, by composed key `<session_id>/<role>`. The registry
        #: stores browsers by string key and knows nothing about what the key
        #: means, on purpose: everything it gets right - one lock per key, the
        #: configuration remembered so a rebuild is the same person, tab
        #: numbering that survives a rebuild - works per browser the moment
        #: the key names one.
        self.registry = BrowserRegistry(factory=factory, defaults=defaults,
                                        on_change=self._identity_changed)
        #: Whether the saved file has been read yet. Once per object, because
        #: a piece of work is restored once and then owns what it holds.
        self.restored = False
        #: Where each browser's pages were the last time anybody looked, by
        #: key. A cache and not a second truth: the pages live in the running
        #: browser, and `remember` runs from a synchronous hook while asking a
        #: browser for its pages is asynchronous, so this is at most one
        #: command stale and a process that ends between two looks comes
        #: back one command behind rather than empty.
        self._seen_tabs: dict[str, list] = {}
        #: Pages a saved file declared and that have not been reopened yet,
        #: by key. Emptied by the wake that uses them, so a browser is
        #: restored ONCE: after that its pages are its own business, and a
        #: wake that kept reopening them would fight whoever is using it.
        self._tabs_owed: dict[str, list] = {}

    # --- declare --------------------------------------------------------------

    def key(self, role: Optional[str] = None) -> str:
        """The registry key for one of the two browsers here.

        Everything addresses through this. A single caller reaching for the
        bare role would look at one browser while its neighbours wrote to
        another, and nothing would raise.
        """
        self.restore()
        return "%s/%s" % (self.session_id, role or DEFAULT_BROWSER_ID)

    def roles(self) -> list:
        """The browsers here, by role, running or only declared.

        Read from the registry's own memory rather than from a list kept
        beside it, because a second list is a second truth: a browser dropped
        by a failed retry would still be in it. Declared counts: a restored
        browser has not started yet, but it holds a slot and it is one of the
        two here.
        """
        self.restore()
        prefix = "%s/" % self.session_id
        return sorted(k[len(prefix):] for k in self.registry.declared()
                      if k.startswith(prefix))

    def restore(self) -> bool:
        """Read the saved browser back, once. Declares it rather than starting
        it: the identity comes back immediately and costs nothing, the engine
        comes back when something is aimed at it. Answers whether anything was
        read."""
        if self.restored:
            return False
        self.restored = True
        saved = store.load(self.session_id)
        if not saved:
            return False
        held = saved.get("browsers") or {}
        if held:
            # ⛔ A FILE WRITTEN BY AN OLDER BUILD CAN NAME EIGHT BROWSERS AND
            # CALL THEM ANYTHING, and this is the only door either can come
            # through. What comes back is ONE browser, as `main`: the one the
            # file says was in focus, else the first by name. The rest are
            # dropped from this PROCESS and not from the file - nothing
            # rewrites it until it changes, and a build that gets rolled back
            # should find what it left. A saved `support` is not restored
            # either: the helper is not an identity.
            keep = saved.get("focus") if saved.get("focus") in held else None
            keep = keep or sorted(held)[0]
            held = {DEFAULT_BROWSER_ID: held[keep]}
        for name, config in held.items():
            key = "%s/%s" % (self.session_id, name)
            # The identity is DECLARED and the pages are OWED, kept apart on
            # purpose: `declare` writes launch settings, and a list of urls is
            # not one of them.
            owed = config.pop("urls", None)
            # ⛔ THIS LAUNCH DECIDES THE ENGINE AND THE WINDOW, NOT THE FILE.
            # `launched_here` is written OVER the file's word, not under it: a
            # file from before 0.50.0 carries `headless: false`, and a file
            # never carries `binary_path` because a path on this machine means
            # nothing on another.
            self.registry.declare(key, dict(config, **plan.launched_here()))
            if owed:
                self._tabs_owed[key] = list(owed)
        return True

    # --- remember -------------------------------------------------------------

    def _identity_changed(self, _key: str) -> None:
        self.remember()

    def remember(self) -> None:
        """Write the browsers held here down, as they stand now.

        Called after anything that changes what is HELD rather than on a
        timer, so the file on disk is never a version that existed only
        between two ticks; hooked into the registry so every way a browser
        comes to exist - `browser_open`, a lazy auto-start - is written down
        without a caller remembering to.

        ⛔ A WRITE THAT FAILS COSTS THE SAVED FILE AND NOTHING ELSE. By the
        time this runs the browser is already built and correct, so a full
        disk must not turn a working `browser_open` into an error.
        """
        prefix = "%s/" % self.session_id
        browsers = {}
        for key in self.registry.declared():
            if not key.startswith(prefix):
                continue
            config = self.registry.config(key) or {}
            wrote = {k: v for k, v in config.items() if k in WHO_A_BROWSER_IS}
            # Where it was, so reopening gives back the work and not only the
            # person. A browser nobody has looked at contributes nothing
            # rather than an empty list: an empty list would mean "it had no
            # pages", which is a different thing from "nobody has asked yet".
            been = self._seen_tabs.get(key)
            if been:
                wrote["urls"] = been
            name = key[len(prefix):]
            if name == SUPPORT_BROWSER_ID:
                # ⛔ THE HELPER IS NOT WRITTEN DOWN. A support browser that
                # came back after a restart would be a second identity, which
                # is what two fixed roles exist to rule out.
                continue
            browsers[name] = wrote
        try:
            if not browsers:
                store.erase(self.session_id)
                return
            store.save(self.session_id, browsers, focus=DEFAULT_BROWSER_ID)
        except Exception:
            pass

    def note_tabs(self, key: str, urls) -> None:
        """Remember where this browser's pages are, and write it down if it
        moved.

        ⛔ ON THE CHANGE AND NOT ON EVERY COMMAND, and the difference is a disk
        write thirteen times a second: every tool call passes through `ready`,
        and the live view's frames are tool calls. Pages move rarely compared
        to how often a browser is touched.
        """
        if urls is None:
            return
        fresh = [u for u in urls if u]
        if self._seen_tabs.get(key) == fresh:
            return
        self._seen_tabs[key] = fresh
        self.remember()

    # --- wake and look --------------------------------------------------------

    async def ready(self, role: Optional[str] = None) -> StealthSession:
        """This browser, started, and back where it was.

        ⛔ ONE FUNNEL. Every command goes through here, so "what it takes to
        hand somebody a usable browser" is a fact known in one place. The
        page a saved file owed is reopened ONCE, and it is one page - the one
        the browser was ON, which is the last the file recorded: a browser
        that has been woken owns where it goes next.
        """
        at = self.key(role)
        owed = self._tabs_owed.pop(at, None)
        session = await self.registry.ensure(at)
        if owed:
            try:
                await actions.navigate(session, owed[-1])
            except Exception:
                # A url that will not load must not cost the browser. It is
                # up, it is the right person, and refusing to hand it back
                # would turn a stale bookmark into a session nobody can use.
                pass
        try:
            # The urls only. `describe_pages` also fetches each page's TITLE,
            # a round trip per page, on every command - including every frame
            # of the live view, twenty-five times a second.
            self.note_tabs(at, session.where_pages_are())
        except Exception:
            pass
        return session

    def looking(self, role: Optional[str] = None) -> Optional[StealthSession]:
        """This browser only if it is ALREADY running. Never starts one.

        ⛔ A QUESTION IS NOT A COMMAND, AND `ready` CANNOT TELL THEM APART. A
        browser this answers `None` for is not gone, it is asleep: declared,
        not needed yet, and the next COMMAND aimed at it starts it as the same
        person. Measured before this existed: drawing the live panes of a
        conversation nobody had asked anything took the machine from 9
        firefox processes to 16.
        """
        return self.registry.peek(self.key(role))

    async def already_open(self, role: Optional[str] = None) -> StealthSession:
        """This browser for a READ: it must already be running, or this
        refuses. Decided by the owner on 2026-09-13: every reading tool needs
        a browser, so it has to have been opened first, with the command that
        opens it."""
        session = self.looking(role)
        if session is None:
            raise RuntimeError(NOTHING_TO_READ % (role or DEFAULT_BROWSER_ID))
        return session

    # --- act ------------------------------------------------------------------

    async def retrying(self, fn: Callable[..., Awaitable], *args,
                       role: Optional[str] = None, **kwargs) -> tuple:
        """Run one action on one browser. If the BROWSER is gone, rebuild it
        once - as the same person, back on its page - and run the action
        again. Answers `(result, rebuilt)`, so the tool can SAY what happened.

        ⛔ ONLY A BROWSER THAT IS GONE IS REBUILT, and until 0.50.0 any
        failure was: a domain that did not resolve counted as a dead browser,
        the healthy one was closed with its cookies and its pages, and a new
        one started to fail the same way. What "gone" means is decided in
        `registry.is_dead`, next to the check that decides it between calls.
        """
        at = self.key(role)
        session = await self.ready(role)
        try:
            return await fn(session, *args, **kwargs), False
        except Exception as failure:
            if not self.registry.is_dead(at, failure):
                # The page refused; the browser is fine. The refusal is the
                # answer.
                raise
            # ⛔ THE PAGES ARE OWED AGAIN, or the recovery gives back half a
            # browser: `drop` keeps the identity on purpose, and the pages
            # were not part of "the same" until this line.
            been = self._seen_tabs.get(at)
            if been:
                self._tabs_owed[at] = list(been)
            await self.registry.drop(at)
            session = await self.ready(role)
            return await fn(session, *args, **kwargs), True

    # --- close ----------------------------------------------------------------

    async def close_all(self) -> None:
        await self.registry.close_all()
