"""Nothing in the product may exist only for the suite.

⛔ THIS IS A GATE ON A CLASS, NOT A LIST OF NAMES THAT WERE REMOVED. Seven
surfaces came out of `src/aihawk` in one audit and every one of them was the
same shape: a function, a constant or a method with no caller in the product,
kept alive by the tests that had grown up around it.

  * `agent.run_task` - a second way to run the agent loop, taking an object
    shaped like the pre-`Link` world. About twenty-five tests, zero product
    callers. It is now `tests/_loop.py`.
  * `Sessions.around` - a constructor whose docstring offered "and so would
    anything embedding this", a user that does not exist. Eleven callers, all
    tests. It is now `tests/_sessions.py`.
  * `SessionPlan.describe` - a second mapping of a plan onto the sentence a
    caller is told, beside the one in `work.open`. Six callers, all tests.
  * `clean.relevance` and `clean.clean_stats` - fifty-seven lines of scoring and
    seven figures of savings, arriving dead with the server on 2026-09-06 and
    never called by anything. `clean_stats` was even in `__all__`.
  * `clean.BLOCK_TAGS` - a tuple nothing read.
  * `Sessions._open_link` as an attribute reassigned from outside - a seam that
    worked and that nothing declared. It is a parameter now.

A list of those seven names would stop those seven. The defect is not the seven:
it is that a surface can be added, be used only by its own tests, and look
exactly like a surface the product depends on. So the question this asks is the
general one - is this named anywhere in `src`? - and the answer has to be yes.

⛔ WHAT IT LOOKS AT, MEASURED, BECAUSE A GREEN SAYS WHAT IT CHECKED AND NOT WHAT
EXISTS. Top-level functions, classes and upper-case constants across the
package: 178 of them in 25 modules on the day it was written, with 18 more
exempt because they are registered (below). METHODS ARE OUT OF SCOPE and that is
not laziness: a method reaches the code as an attribute, and `plan.describe(...)`
and `SessionPlan.describe(...)` are the same attribute name, so a scan cannot
tell a dead method from a live function beside it. `SessionPlan.describe` was
found by reading, and this gate would not have found it. Anything nested inside
a function is out of scope too - it cannot be reached from outside in the first
place.

⛔ WHAT EXCUSES A DEFINITION IS BEING REGISTERED, WHICH IS STRUCTURAL. A
decorator spelled `.tool`, `.command` or `.group` hands the object to somebody
else - FastMCP's registry, click's - and the call that follows happens over a
wire or from a shell, where no scan of this tree can see it. `@dataclass`,
`@contextmanager` and `@asynccontextmanager` do NOT excuse anything: they wrap
the object and hand it straight back, so it is still called by name and still has
to be.

⛔ AND `__all__` IS NOT EVIDENCE. It is the claim under audit - "this module
exports this" - so a name that appears only there counts as unused. That is
exactly where `clean_stats` was hiding: exported, tested, called by nobody.
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "aihawk"

#: A decorator spelling that hands the object to a registry. See the module
#: docstring: this is the whole exemption, and it is deliberately not a list of
#: function names.
REGISTERED = (".tool", ".command", ".group")


def _defined(tree: ast.Module):
    """(name, line, registered) for every top-level surface of one module."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            registered = any(any(m in ast.unparse(d) for m in REGISTERED)
                             for d in node.decorator_list)
            yield node.name, node.lineno, registered
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                # Upper-case only: a lower-case module-level assignment is
                # usually a value being built, not a surface being offered.
                if isinstance(t, ast.Name) and t.id.isupper() and len(t.id) > 2:
                    yield t.id, node.lineno, False


def _named(tree: ast.Module):
    """Every name this module NAMES: reads, attributes, imports, and the words
    of its strings - except the strings inside `__all__`, for the reason in the
    module docstring.

    A definition never names itself here: a `def` is not an `ast.Name`, and an
    assignment's target is a `Store`, not a `Load`. So a count of zero means
    nothing else in the package mentions it.
    """
    in_all = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            in_all.update(id(child) for child in ast.walk(node.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            yield node.id
        elif isinstance(node, ast.Attribute):
            yield node.attr
        elif isinstance(node, ast.alias):
            yield node.name.split(".")[-1]
            if node.asname:
                yield node.asname
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # Strings count, because a name can genuinely be reached through
            # one. `__all__` is the exception and it is handled above.
            if id(node) not in in_all:
                yield from node.value.split()


def unnamed(sources: dict) -> list:
    """Every top-level surface in these modules that no module names.

    Takes the sources as a mapping so the known-bad cases below are dictionaries
    rather than a directory somebody has to write to disk first.
    """
    trees = {where: ast.parse(text) for where, text in sources.items()}
    named = set()
    for tree in trees.values():
        named.update(_named(tree))
    out = []
    for where, tree in trees.items():
        for name, line, registered in _defined(tree):
            if not registered and name not in named:
                out.append("%s:%d %s" % (where, line, name))
    return sorted(out)


def _product() -> dict:
    return {str(p.relative_to(SRC)): p.read_text(encoding="utf-8")
            for p in sorted(SRC.rglob("*.py"))}


def test_every_surface_the_product_offers_is_one_the_product_names():
    """The gate itself. A failure names the file, the line and the surface, and
    the fix is one of two things: call it, or delete it. Moving it into the
    suite, as the seven above were moved, counts as deleting it."""
    left = unnamed(_product())
    assert not left, (
        "%d surface(s) in src/aihawk that nothing in src/aihawk names:\n  %s\n"
        "Each is either dead or exists only for the tests. If the suite wants "
        "it, it belongs in the suite." % (len(left), "\n  ".join(left)))


def test_the_gate_is_looking_at_the_whole_package():
    """⛔ A GREEN SAYS WHAT IT CHECKED. A scan that silently stopped finding
    definitions - a walk rooted at the wrong directory, an AST shape that stopped
    matching - would print the same clean line as a healthy package. The floors
    are well under the measured 178 across 25 modules, so ordinary growth never
    touches this and a collapse does."""
    sources = _product()
    assert len(sources) >= 20, "only %d modules found under %s" % (len(sources), SRC)
    judged = sum(1 for text in sources.values()
                 for _, _, registered in _defined(ast.parse(text)) if not registered)
    assert judged >= 120, "only %d definitions judged; the scan has gone blind" % judged


# --- known-bad inputs. A gate that has only ever printed PASS is not a gate ---

def test_a_function_nobody_calls_is_caught():
    """`clean.relevance`, in miniature: fifty-seven lines nothing ever called."""
    assert unnamed({"a.py": "def relevance(node):\n    return 1\n"}) == ["a.py:1 relevance"]


def test_a_constant_nobody_reads_is_caught():
    """`clean.BLOCK_TAGS`, in miniature."""
    assert unnamed({"a.py": "BLOCK_TAGS = ('div', 'p')\n"}) == ["a.py:1 BLOCK_TAGS"]


def test_a_class_nobody_builds_is_caught():
    assert unnamed({"a.py": "class Helper:\n    pass\n"}) == ["a.py:1 Helper"]


def test_exporting_it_is_not_using_it():
    """⛔ THE HIDING PLACE `clean_stats` USED. It was in `__all__`, it had a
    test, and no caller. If `__all__` counted as a reference this gate would
    pass it, which is the whole reason for the exception in `_named`."""
    source = "__all__ = ['clean_stats']\n\n\ndef clean_stats(a, b):\n    return {}\n"
    assert unnamed({"a.py": source}) == ["a.py:4 clean_stats"]


def test_a_surface_only_the_tests_use_is_caught():
    """The seven removed this day were all this: alive in `tests/`, unnamed in
    `src`. The mapping handed in is the PRODUCT, so a caller outside it cannot
    keep a surface alive - which is the point."""
    product = {"agent.py": "def run_task(mcp, task):\n    return task\n"}
    assert unnamed(product) == ["agent.py:1 run_task"]


def test_a_decorator_that_only_wraps_does_not_excuse_it():
    """⛔ `@dataclass` and `@contextmanager` hand the object straight back, so it
    is still called by name. Known-bad is excusing anything decorated, which
    would have let `SessionPlan` through had it ever lost its callers."""
    source = ("from dataclasses import dataclass\n\n\n"
              "@dataclass\nclass Plan:\n    x: int = 0\n")
    assert unnamed({"a.py": source}) == ["a.py:5 Plan"]


# --- the cases that must NOT fire --------------------------------------------

# ⛔ EACH FIXTURE BELOW ENDS AT A REGISTERED ENTRY POINT, exactly as the package
# does. Without one the toy module's own outermost function has no caller either
# and the gate reports IT - correctly, which is why these are written this way
# rather than by loosening the assertion to ignore whatever came back.

def test_a_function_called_from_another_module_is_left_alone():
    assert unnamed({
        "a.py": "def file_for(kind, at):\n    return kind + at\n",
        "b.py": "from .a import file_for\n\n\n@mcp.tool()\n"
                "def go():\n    return file_for('x', 'y')\n",
    }) == []


def test_a_function_called_only_inside_its_own_module_is_left_alone():
    """A private helper with one caller beside it is not dead. Known-bad is
    counting references across modules only, which would condemn most of
    `clean.py`."""
    assert unnamed({
        "a.py": "def _drop(t):\n    return t\n\n\n@mcp.tool()\n"
                "def clean(t):\n    return _drop(t)\n",
    }) == []


def test_a_registered_tool_is_left_alone():
    """The sixteen MCP tools have no caller in this tree and never will: they
    are called over a wire. Known-bad is a gate that demands an in-tree caller,
    which would condemn the product's entire public surface."""
    source = ("@mcp.tool(annotations=_says('Open a browser'))\n"
              "async def browser_open(browser=None):\n    return ''\n")
    assert unnamed({"server.py": source}) == []


def test_a_click_command_is_left_alone():
    source = ("@main.command()\n@click.option('--port')\n"
              "def ui(port):\n    return port\n")
    assert unnamed({"cli.py": source}) == []


def test_a_name_reached_through_a_string_is_left_alone():
    """⛔ THE CASE THAT MAKES THE STRING RULE NARROW. A name can genuinely be
    reached by string - through `getattr`, through a table of verbs - and
    condemning it would push somebody to widen the exemptions instead. Only
    `__all__` is excluded, because only `__all__` is a claim about export rather
    than a use."""
    assert unnamed({
        "a.py": "def browser_navigate():\n    return 1\n",
        "b.py": "VERBS = {'browser_navigate': 'goes to a URL'}\n\n\n@mcp.tool()\n"
                "def say(name):\n    return VERBS[name]\n",
    }) == []
