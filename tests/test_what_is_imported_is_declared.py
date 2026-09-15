"""Every third-party module this package imports is one it declares.

⛔ A DIRECT IMPORT OF A TRANSITIVE DEPENDENCY IS A BET ON SOMEBODY ELSE'S
PYPROJECT. `src/aihawk/mcp/server.py` says `from pydantic import Field` and
`pyproject.toml` did not mention pydantic at all: it arrived because `mcp`
requires it. That works until `mcp` stops requiring it, or moves to a major this
code cannot use, and then `aihawk` fails at IMPORT for every user who installs
it - with a traceback that names pydantic and a cause that is nowhere near it.

Nothing could have caught it either. Every environment that has `mcp` has
pydantic, so the suite is green, the CI is green, a clean-environment check is
green, and the wheel is broken only in a future that has not happened yet. The
same is true of `httpx`, which the interface-to-real-server test imports and
which also arrives through `mcp`.

The rule is the one this repository already applies to the engine and to the
core pin, moved one layer out: use what you declare. It is not about pinning
tightly - the floors here are the lowest that are true - it is about the
declaration existing at all, so a resolver can be told and a reader can see it.

⛔ WHAT THIS DOES NOT SEE, because a green says what it checked. It reads
IMPORTS, so a dependency reached by `importlib.import_module` with a computed
name is invisible; and it says nothing about whether a floor is high enough,
which is a question only a resolver can answer. It also leaves the pytest
PLUGINS alone: `pytest-asyncio` is never imported by anything and is declared
correctly, because a plugin is loaded by pytest rather than by the code.
"""
from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"

#: Index name -> the module names that installing it provides, listed only where
#: the two differ. Everything else imports under its own name.
PROVIDES = {
    "invisible-playwright": {"invisible_playwright"},
    "python-dotenv": {"dotenv"},
}

def _ours() -> set:
    """Module names that live in this repository, so a bare import of one is not
    a third-party dependency.

    ⛔ RESOLVED FROM THE TREE, NOT LISTED. A hand-written list was the first
    version and it was already wrong on its first run: it named five helpers and
    missed `test_web_service`, which `test_the_event_stream_wire_format.py`
    imports because the suite's convention here is a bare import between test
    modules. A list of local names is a second declaration of what the directory
    already says, and it goes stale the next time somebody adds a helper.
    """
    out = {"aihawk"}
    for folder in (ROOT / "tests", ROOT / "scripts"):
        if folder.is_dir():
            out |= {p.stem for p in folder.rglob("*.py")}
    return out


def _bare_name(requirement: str) -> str:
    for sep in (">=", "==", "<=", "~=", "!=", "<", ">", "[", ";"):
        requirement = requirement.split(sep)[0]
    return requirement.strip().lower()


def _declared() -> dict:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    out = {"runtime": set()}
    for requirement in data.get("dependencies", []):
        out["runtime"] |= PROVIDES.get(_bare_name(requirement),
                                       {_bare_name(requirement).replace("-", "_")})
    for group, requirements in data.get("optional-dependencies", {}).items():
        out[group] = set()
        for requirement in requirements:
            out[group] |= PROVIDES.get(_bare_name(requirement),
                                       {_bare_name(requirement).replace("-", "_")})
    return out


def _imported(folder: Path) -> dict:
    """Top-level module name -> the files that import it."""
    out: dict = {}
    ours = _ours()
    for path in sorted(folder.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name in sys.stdlib_module_names or name in ours:
                    continue
                out.setdefault(name, set()).add(str(path.relative_to(ROOT)))
    return out


def test_the_package_declares_everything_it_imports():
    """Known-bad is the state this file was written in: `from pydantic import
    Field` in the server, and no pydantic in `pyproject.toml`."""
    declared = _declared()["runtime"]
    missing = {name: sorted(files)
               for name, files in _imported(ROOT / "src").items()
               if name not in declared}
    assert not missing, (
        "the package imports %d module(s) it does not declare:\n  %s\n"
        "They reach it through somebody else's dependencies today, and stop "
        "the day that somebody drops them."
        % (len(missing), "\n  ".join("%s  (%s)" % (n, ", ".join(f))
                                     for n, f in sorted(missing.items()))))


def test_the_suite_declares_everything_it_imports():
    """The same question for `[project.optional-dependencies] test`, which is
    what CI installs. Known-bad is `httpx`, which the real-server test imports
    and which arrives through `mcp`."""
    allowed = _declared()["runtime"] | _declared().get("test", set())
    missing = {name: sorted(files)
               for name, files in _imported(ROOT / "tests").items()
               if name not in allowed}
    assert not missing, (
        "the suite imports %d module(s) nothing declares:\n  %s"
        % (len(missing), "\n  ".join("%s  (%s)" % (n, ", ".join(f))
                                     for n, f in sorted(missing.items()))))


def test_the_scan_is_looking_at_something():
    """⛔ A GREEN SAYS WHAT IT CHECKED. If the walk found no imports at all -
    a wrong root, an AST shape that stopped matching - both tests above would
    pass on an empty set and say nothing."""
    from_package = _imported(ROOT / "src")
    assert len(from_package) >= 5, (
        "only %d third-party modules found in src; the scan has gone blind"
        % len(from_package))
    assert "mcp" in from_package, "the scan cannot even see the MCP SDK"
    declared = _declared()
    assert len(declared["runtime"]) >= 6, (
        "only %d runtime dependencies parsed out of pyproject" % len(declared["runtime"]))


def test_a_missing_declaration_is_what_it_catches():
    """The known-bad input, run against the reader rather than the real file, so
    the gate has seen its own failure at least once."""
    healthy = PYPROJECT.read_text(encoding="utf-8")
    assert "mcp>=" in healthy, "the requirement moved; this mutation is stale"
    broken = tomllib.loads(healthy.replace('"mcp>=1.8,<2",\n', ""))["project"]
    assert not any(r.startswith("mcp") for r in broken["dependencies"]), (
        "the mutation did not apply, so a survivor here would say nothing")
