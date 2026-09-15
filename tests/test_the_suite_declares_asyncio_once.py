"""`asyncio_mode = "auto"` is declared once, and 43 tests depend on it.

⛔ THIS GATE EXISTS BECAUSE SOMETHING WAS DELETED. The same fact - "the async
tests in this suite are asyncio tests" - used to be declared 44 times: once in
`pyproject.toml`, and again as `@pytest.mark.asyncio` or a module-level
`pytestmark` at 43 sites. The copies could disagree with the original, and they
did: nine of them sat on SYNCHRONOUS functions, so every run printed nine
warnings saying the marker did not belong there. Noise is not harmless - it is
where a real warning hides.

The 43 came out. What makes that safe is this file rather than a hope: without
`asyncio_mode = "auto"`, pytest-asyncio's strict mode SKIPS an unmarked async
test instead of failing it, so the suite would go green while 43 tests quietly
stopped running. That is a false green of exactly the kind this project keeps
finding, so the surviving declaration gets a gate, the way a rule that moves
always does here.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _pytest_config(text: str) -> dict:
    return tomllib.loads(text).get("tool", {}).get("pytest", {}).get(
        "ini_options", {})


def test_the_one_declaration_is_still_there():
    """Known-bad is deleting the line, which is what a tidy-up would do to a
    setting nothing appears to reference any more."""
    config = _pytest_config(PYPROJECT.read_text(encoding="utf-8"))
    assert config.get("asyncio_mode") == "auto", (
        "asyncio_mode is %r. 43 async tests carry no marker of their own and "
        "rely on this; under strict mode pytest-asyncio SKIPS them, and the "
        "suite stays green while they stop running."
        % config.get("asyncio_mode"))


def test_the_gate_notices_when_it_is_gone():
    """The known-bad input, run against the reader rather than against the real
    file: a gate that has only ever seen the healthy case is not a gate."""
    healthy = PYPROJECT.read_text(encoding="utf-8")
    broken = healthy.replace('asyncio_mode = "auto"', 'asyncio_mode = "strict"')
    assert broken != healthy, "the mutation did not apply; the literal moved"
    assert _pytest_config(broken).get("asyncio_mode") == "strict"

    removed = healthy.replace('asyncio_mode = "auto"\n', "")
    assert removed != healthy, "the mutation did not apply; the line moved"
    assert _pytest_config(removed).get("asyncio_mode") is None


def test_nobody_has_started_declaring_it_again():
    """The other half: the 43 copies must not come back one file at a time.

    A single re-added marker is harmless on its own, which is precisely how the
    other 42 would follow it."""
    here = Path(__file__).resolve().parent
    guilty = []
    for path in sorted(here.rglob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        if "mark.asyncio" in text:
            guilty.append(str(path.relative_to(here)))
    assert not guilty, (
        "%d file(s) declare asyncio again, next to the one declaration in "
        "pyproject.toml:\n  %s" % (len(guilty), "\n  ".join(guilty)))
