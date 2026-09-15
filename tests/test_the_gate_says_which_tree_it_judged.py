"""A clean bill names the tree it is about, or it is not an answer.

⛔ `scripts/check_english_only.py` CAN ONLY JUDGE THE REPOSITORY IT LIVES IN, AND
SAID NOTHING ABOUT IT. Its root comes from `__file__` and its file list from
`git ls-files` run inside that root, so invoking this copy from another checkout
scanned THIS one and printed `english only: clean` about a tree the caller never
asked about.

MEASURED 2026-09-15, and the caller was this project. Run from the sibling
package `invisible_core`, it said clean. Asked properly - the same code with its
root pointed at that repository - it reports 29 files carrying Italian prose,
eleven of them inside the shipped package. The sentence was believed for two
steps before the contradiction surfaced, which is what a false green costs: not
a wrong answer, an answer to a different question.

WHY IT WAS NEVER CAUGHT, and the part worth keeping: the gate exists TWICE, once
here and once in the wrapper, already byte-different, and each copy judges its
own tree. A rule enforced by a copied script reaches exactly the repositories
somebody remembered to copy it into, and `invisible_core` was not one of them -
it has no copy and no CI job for it. The single home for a rule that all three
must obey is `invisible_core.hooks`, which both Python packages already run on
every push; that consolidation is a core release and is not done here.

What IS done here is the false green. It refuses now, the way the pin gate
already does, and names both trees; a deliberate cross-repo run says so with
`--root`.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_english_only.py"


def _load():
    spec = importlib.util.spec_from_file_location("gate_lang", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_from_its_own_repository_it_just_works(monkeypatch):
    """The case that must NOT fire: CI runs it from the repository root, and a
    refusal there would be a gate red on correct usage."""
    monkeypatch.chdir(ROOT)
    assert _load()._judged_root(None) == ROOT


def test_from_another_repository_it_refuses_instead_of_answering(tmp_path,
                                                                 monkeypatch):
    """⛔ THE KNOWN-BAD, AND IT IS THE REAL ONE. Before this, the call returned
    quietly and the scan went on to print a clean bill for the wrong tree."""
    other = tmp_path / "somebody-elses-repo"
    other.mkdir()
    subprocess.run(["git", "init", "-q", str(other)], check=True)
    monkeypatch.chdir(other)

    with pytest.raises(SystemExit) as refused:
        _load()._judged_root(None)

    said = str(refused.value)
    assert "REFUSED" in said
    assert str(ROOT) in said, "the refusal must name the tree it would have scanned"
    assert "somebody-elses-repo" in said, "and the tree the caller is standing in"
    assert "--root" in said, "and how to mean it on purpose"


def test_an_explicit_root_is_honoured(tmp_path):
    """A cross-repo run is legitimate - a maintainer checking a sibling - and
    must stay possible. What changed is that it has to be said."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert _load()._judged_root(str(elsewhere)) == elsewhere.resolve()


def test_outside_any_repository_it_falls_back_rather_than_crashing(tmp_path,
                                                                   monkeypatch):
    """The case that must NOT fire: `git rev-parse` failing is not a reason to
    refuse, it just means there is nothing to compare against."""
    monkeypatch.chdir(tmp_path)
    module = _load()
    monkeypatch.setattr(module.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 128, "", ""))
    assert module._judged_root(None) == ROOT


def test_the_clean_line_names_the_tree():
    """Known-bad is going back to the bare sentence. The whole defect was a
    green that did not say what it was about."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'print("english only: clean (%s)" % ROOT)' in source, (
        "the success line must name the repository it judged")
