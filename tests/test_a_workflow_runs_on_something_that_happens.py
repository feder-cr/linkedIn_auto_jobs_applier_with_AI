"""A workflow meant to run by itself must trigger on an event that occurs here.

⛔ `publish-wiki.yml` TRIGGERED ON `release: published` FOR SIXTY-THREE RUNS AND
THAT TRIGGER NEVER FIRED ONCE. Every run was a manual dispatch. It is not a
mistake in a condition: GitHub does not start a workflow from an event created
with the built-in GITHUB_TOKEN, and the release here is created by
`publish.yml`, which is why its author is github-actions[bot]. The workflow's
own header said "it runs on a published release", and that sentence was false
from the day it was written.

Nothing could go red about it. A workflow that is never triggered produces no
failing run; it produces no run at all, and an absence is not something a check
list shows. It was found by asking a different question - of every job this
repository declares, how many times has it actually run - and by noticing that
one of seventeen never appeared.

WHAT IT COST, MEASURED. The wiki was last built from ae33811 on 2026-09-13. By
2026-09-15 eight releases had gone by and 16 pages had changed, 81 insertions
and 68 deletions, including the published character and token figures that
0.64.0 and 0.65.0 moved. Readers were being shown the previous numbers, and the
only thing keeping the wiki anywhere near current was somebody remembering to
press the button.

⛔ WHAT THIS GATE CANNOT SEE, because a green says what it checked. It reads the
`on:` block as TEXT - this repository declares no YAML parser and a test is not
the place to add one - so it knows which triggers are named, not whether a
`paths:` filter matches anything real. That second half is the same defect one
step along, so the one filter that exists is checked against the tree by name.
It also says nothing about whether a workflow WORKS, only that something can
start it.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

#: Triggers that start a run without a person. `workflow_dispatch` is a person
#: pressing a button, so it does not count as automatic; `release` does not
#: count either, for the reason in the module docstring.
AUTOMATIC = ("push", "pull_request", "schedule", "workflow_call",
             "workflow_run", "issues", "discussion")


def _triggers(text: str) -> set:
    """The event names in the `on:` block, read from indentation.

    The block runs from a line that is exactly `on:` to the next line that
    starts at column zero, and each event is a key indented by two.
    """
    out, inside = set(), False
    for line in text.splitlines():
        if re.match(r"^on:\s*$", line):
            inside = True
            continue
        if inside:
            if line and not line.startswith(" ") and not line.startswith("#"):
                break
            found = re.match(r"^  ([a-z_]+):", line)
            if found:
                out.add(found.group(1))
    return out


def _workflows() -> dict:
    return {p.name: p.read_text(encoding="utf-8")
            for p in sorted(WORKFLOWS.glob("*.yml"))}


def test_no_workflow_waits_only_for_an_event_this_repository_cannot_raise():
    """Known-bad is the state this file was written in: `publish-wiki.yml` with
    `release` and `workflow_dispatch` and nothing else."""
    stranded = []
    for name, text in _workflows().items():
        triggers = _triggers(text)
        if not triggers:
            stranded.append("%s declares no triggers at all" % name)
            continue
        if not triggers & set(AUTOMATIC):
            stranded.append("%s: %s" % (name, ", ".join(sorted(triggers))))
    assert not stranded, (
        "%d workflow(s) can only be started by hand, or by a release that "
        "GITHUB_TOKEN creates and so never announces:\n  %s"
        % (len(stranded), "\n  ".join(stranded)))


def test_the_wiki_follows_the_documents_it_mirrors():
    """The same defect one step along: a `paths:` filter that matches nothing
    is a trigger that never fires, and it reads exactly like one that works.

    Known-bad is renaming `docs/` without touching this list, or narrowing the
    filter to a directory that is not where the pages are."""
    text = _workflows()["publish-wiki.yml"]
    assert "push" in _triggers(text), (
        "the wiki is built from the docs and nothing pushes it: it went stale "
        "through eight releases the last time this was true")
    listed = re.findall(r'^\s+- "([^"]+)"', text, re.M)
    assert any(p.startswith("docs/") for p in listed), (
        "the push filter does not name docs/: %s" % listed)
    for pattern in listed:
        head = pattern.split("*")[0].rstrip("/")
        if not head:
            continue
        assert (ROOT / head).exists(), (
            "the filter names %r, which is not in the tree - so it can never "
            "match and the trigger is decorative" % pattern)


def test_every_selection_the_suite_hides_is_one_some_workflow_asks_for():
    """A marker that `addopts` deselects, and that no job names, is unreachable.

    ⛔ THE SIXTEEN `ui` TESTS WERE EXACTLY THAT. `addopts` is
    `-m 'not ui and not e2e'`, and the only job that asked for anything asked
    for `-m e2e tests/mcp_server`. So `tests/test_ui_drive.py` - sixteen tests
    that drive a real browser through a real server - was selected by no run
    anywhere, and all sixteen had rotted into an error at fixture setup without
    a single red anywhere.

    A deselected test does not fail. It is absent, and a summary calls that
    "deselected", which reads like a decision rather than a gap. This is the
    same shape as the trigger that never fires, one file over: something is
    declared, and nothing executes it.

    Known-bad is removing `-m ui` from the e2e job, or adding a third marker to
    `addopts` and no job to run it.
    """
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    # `[a-z_0-9]+` and not `[a-z_]+`: the first version stopped at the digit in
    # `e2e` and reported a marker called `e`, which is the gate accusing a name
    # that does not exist.
    hidden = set(re.findall(r"not\s+([a-z_0-9]+)",
                            re.search(r'addopts\s*=\s*"([^"]*)"',
                                      pyproject).group(1)))
    assert hidden, "no marker is deselected; this gate has nothing to guard"

    # ⛔ COMMENTS STRIPPED, AND THIS GATE FELL FOR THEM ON ITS FIRST KNOWN-BAD.
    # The first version searched the raw YAML, and the comment written beside
    # the job - the one explaining that it now runs the ui selection - satisfied
    # the search on its own. Removing the command left the sentence about it,
    # and the gate stayed green. It is the most repeated defect in this project,
    # met inside the gate written to find things that never run.
    asked = " ".join(
        "\n".join(line for line in text.splitlines()
                  if not line.lstrip().startswith("#"))
        for text in _workflows().values())
    orphaned = sorted(m for m in hidden
                      if not re.search(r"-m\s+'?%s\b" % re.escape(m), asked))
    assert not orphaned, (
        "%d marker(s) deselected by addopts that no workflow ever asks for: "
        "%s\nTests behind them are run by nobody and rot without going red."
        % (len(orphaned), ", ".join(orphaned)))


def test_the_reader_is_looking_at_the_real_block():
    """⛔ A GREEN SAYS WHAT IT CHECKED. If `_triggers` stopped matching - an
    `on:` written inline, a file reformatted - every workflow would come back
    with an empty set and the first test would read that as a failure while the
    second would be judging nothing. The floors say the reader still works."""
    found = _workflows()
    assert len(found) >= 4, "only %d workflow files found" % len(found)
    for name, text in found.items():
        assert _triggers(text), "no triggers parsed out of %s" % name
    assert "push" in _triggers(found["ci.yml"]), (
        "ci.yml is known to run on push; the reader disagrees, so it is broken")


def test_the_rule_is_what_it_says_and_not_a_shape():
    """The known-bad input, run against the reader: a workflow with only
    `release` and `workflow_dispatch` must be caught, and adding `push` must be
    what clears it."""
    stranded = "on:\n  release:\n    types: [published]\n  workflow_dispatch: {}\n"
    assert not _triggers(stranded) & set(AUTOMATIC)
    fixed = "on:\n  push:\n    branches: [main]\n" + stranded[len("on:\n"):]
    assert _triggers(fixed) & set(AUTOMATIC) == {"push"}
