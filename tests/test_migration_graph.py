"""The migration graph has one head, and the join names every line that would be one.

Written with the join revision beside it, for the branch that first composes the room's
August stack. Both assertions are load-bearing and the second one looks redundant until you
read why it is not — see the second test's docstring.
"""

from __future__ import annotations

from alembic.config import Config
from alembic.script import Script, ScriptDirectory


def _graph() -> ScriptDirectory:
    return ScriptDirectory.from_config(Config("alembic.ini"))


def _parents(revision: Script) -> set[str]:
    down = revision.down_revision
    if down is None:
        return set()
    return set(down) if isinstance(down, tuple) else {down}


def test_the_graph_has_a_single_head() -> None:
    """`alembic upgrade head` refuses outright while there is more than one.

    It refuses **before touching anything**, so this is the failure that costs nothing to
    have and everything to miss: it does not corrupt a database, it just means nobody can
    bring one up.
    """
    heads = _graph().get_heads()

    assert len(heads) == 1, f"expected one head, found {len(heads)}: {sorted(heads)}"


def test_the_join_names_every_line_that_would_otherwise_be_a_head() -> None:
    """**Not redundant with the head count, and this was measured rather than assumed.**

    A join that names an extra parent which is *not* a tip — say `_0002` beside the three
    real ones — leaves the graph with exactly one head. `alembic heads` is content, the
    upgrade job is green, and the join is quietly wrong about the shape of the thing it
    joins. Only this assertion goes red there.

    The expectation is **derived and never listed**. Whatever nothing else descends from is a
    line that has to be joined, so a parent dropped from the join reappears here and a fourth
    line nobody joined appears here too. Writing the three names instead would be blind to
    both, and would have to be edited by whoever adds the fourth — which is the edit nobody
    remembers to make.
    """
    script = _graph()
    join = script.get_revision(script.get_heads()[0])
    everything = {revision.revision: revision for revision in script.walk_revisions()}

    referenced: set[str] = set()
    for revision in everything.values():
        if revision.revision != join.revision:
            referenced |= _parents(revision)
    would_be_heads = {rev for rev in everything if rev != join.revision and rev not in referenced}

    assert _parents(join) == would_be_heads, (
        f"the join points at {sorted(_parents(join))} "
        f"but the lines with no successor are {sorted(would_be_heads)}"
    )
