"""A clean bill names the tree it is about, or it is not an answer.

⛔ THE FALSE GREEN THIS FILE WAS WRITTEN FOR. The check used to be
`scripts/check_english_only.py`, a script whose root came from `__file__` and
whose file list came from `git ls-files` run inside that root - so invoking it
from another checkout scanned THIS one and printed `english only: clean` about a
tree the caller never asked about.

Measured 2026-09-15, and the caller was this project. Run from the sibling
package `invisible_core`, it said clean. Asked properly, it reported 29 files
carrying Italian prose, eleven inside the shipped package. The sentence was
believed for two steps: not a wrong answer, an answer to a different question.

⛔ AND THE REFUSAL THIS FILE USED TO ASSERT IS GONE, DELIBERATELY. The script
grew a guard that REFUSED when the tree you stood in and the tree it would scan
disagreed. That was a correct patch on a wrong shape. The previous version of
this docstring named the real fix and said it was not done yet: "the single home
for a rule that all three must obey is invisible_core, which both Python
packages already run on every push; that consolidation is a core release and is
not done here." It is done now, in invisible-core 30.23.0: the gate is
`invisible_core.english`, it takes the tree as an ARGUMENT defaulting to the git
toplevel you are standing in, and there is nothing left to disagree with. So the
test that asserted the refusal is replaced by the one that asserts the property
the refusal was protecting - a cross-repo run answers about the repository it
was pointed at, and says which one that was.

That property is what still needs holding, because it is the only thing standing
between a green and a green about somewhere else.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from invisible_core import english

_REPO = Path(__file__).resolve().parents[1]


def _run(*args, cwd):
    """The gate as a COMMAND, which is how CI and the pre-push hook reach it."""
    return subprocess.run([sys.executable, "-m", "invisible_core.english", *args],
                          cwd=str(cwd), capture_output=True, text=True)


def test_from_its_own_repository_it_judges_that_repository():
    """The ordinary case: no argument, and the answer is about here."""
    r = _run(cwd=_REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    assert str(_REPO) in r.stdout, r.stdout


def test_from_another_repository_it_answers_about_THAT_one_and_says_so(tmp_path):
    """⛔ THE REPLACEMENT FOR THE OLD REFUSAL, and the reason it can be replaced.

    The script could only ever judge where it lived, so pointing it elsewhere
    was a mistake to catch. The module is given the tree, so pointing it
    elsewhere is an ordinary, correct request - and the thing that keeps it
    honest is that the answer names the tree it is about. An answer that named
    no tree is what made the false green survive two steps.
    """
    other = tmp_path / "somewhere-else"
    other.mkdir()
    subprocess.run(["git", "init", "-q", str(other)], check=True, capture_output=True)
    (other / "clean.py").write_text("# Plain English, nothing to find here.\n",
                                    encoding="utf-8")
    subprocess.run(["git", "add", "clean.py"], cwd=str(other), check=True,
                   capture_output=True)

    r = _run("--root", str(other), cwd=_REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    assert str(other) in r.stdout, r.stdout
    assert str(_REPO) not in r.stdout, (
        "it answered about the repository it lives in, not the one it was "
        "given: " + r.stdout)


def test_a_cross_repo_run_reports_the_OTHER_tree_s_italian(tmp_path):
    """The must-fire half of the same question: pointed at a guilty tree it
    accuses that tree, rather than reporting its own clean state."""
    other = tmp_path / "guilty"
    other.mkdir()
    subprocess.run(["git", "init", "-q", str(other)], check=True, capture_output=True)
    (other / "guilty.py").write_text(english._ITA, encoding="utf-8")
    subprocess.run(["git", "add", "guilty.py"], cwd=str(other), check=True,
                   capture_output=True)

    r = _run("--root", str(other), cwd=_REPO)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "guilty.py" in r.stdout, r.stdout


def test_outside_any_repository_it_refuses_rather_than_guessing(tmp_path):
    """With no git above it there is no tree to judge, and inventing one would
    be the same failure in a different direction."""
    r = _run(cwd=tmp_path)
    assert r.returncode != 0
    assert "--root" in (r.stdout + r.stderr), r.stdout + r.stderr


def test_the_clean_line_names_the_tree_and_what_it_read():
    """A green says what it checked. The bare sentence was believed about the
    wrong repository once already; a perimeter inferred from a green is a hope,
    so the count of files read is part of the answer."""
    r = _run(cwd=_REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "english only: clean" in r.stdout
    assert str(_REPO) in r.stdout
    assert "file(s) read" in r.stdout, r.stdout


def test_this_repository_declares_no_exclusions_and_needs_none():
    """⛔ THE DRIFT THAT CAME WITH THE COPY. This repository's script carried
    FIVE exclusions, and four named paths that exist only in the wrapper -
    `src/invisible_playwright/_pw/`, `_driver/`, `_juggler/injected.js`,
    `tests/test_fork.py`. They were never true here; they arrived with the file.

    A dead exclusion never makes anything red, which is exactly why nobody found
    it. The shared gate refuses one, and this repository now declares nothing.
    """
    config = english.config_for(_REPO)
    assert config.excluded == (), config.excluded
    assert english.dead_exclusions(_REPO, config) == []
    guilty = english.scan(_REPO, english.tracked(_REPO), config)
    assert not guilty, (
        "%d file(s) are not in English with nothing exempt:\n  " % len(guilty)
        + "\n  ".join("%s: %s" % (p, ", ".join(w[:5])) for p, w in guilty))


@pytest.mark.parametrize("name,path,text",
                         [(n, p, t) for n, p, t, _ in english.KNOWN_BAD],
                         ids=[n.replace(" ", "_") for n, _, _, _ in english.KNOWN_BAD])
def test_the_gate_still_has_teeth(name, path, text):
    """The corpus travelled with the gate, so it is still exercised from here:
    a gate that has only ever printed clean is not a gate."""
    assert english.inspect(path, text, english.CORPUS_CONFIG)[0], name
