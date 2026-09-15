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
