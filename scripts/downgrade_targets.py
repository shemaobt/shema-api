"""The revisions the migrations job has to walk back to, one per line.

``alembic downgrade -1`` means one step back from the head, and that has no answer
when the head is a merge revision: it has two parents, and Alembic refuses with
"Ambiguous walk". Where it did resolve it would undo the merge — which does nothing —
and the job would report that as the newest migration having been checked.

So the targets are derived from the graph instead of written into the workflow. For a
merge head this prints one ``<parent>-1`` per parent, which puts the last real
migration of every joined line back under test. For an ordinary head it prints ``-1``,
which is what the job always did.

Deriving rather than naming is the whole point of this file, and the reason is worth
having measured rather than assumed. A target written into the workflow does not stop
undoing the newest migration when a line grows one — it undoes that one *and* everything
back to the revision it names, one extra step per migration gained. So the check drifts
from "the newest migration undoes what it did" into a slow re-run of the line's history,
and the first old downgrade that no longer applies cleanly fails the job for a reason
that has nothing to do with the change under review.
"""

from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory


def downgrade_targets() -> list[str]:
    """One Alembic revision spec per line the downgrade check should walk."""
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    heads = script.get_heads()
    if len(heads) != 1:
        raise SystemExit(
            f"expected a single head, found {len(heads)}: {', '.join(sorted(heads)) or '(none)'}"
        )

    parents = script.get_revision(heads[0]).down_revision
    if not isinstance(parents, tuple):
        return ["-1"]
    return [f"{parent}-1" for parent in parents]


if __name__ == "__main__":
    print("\n".join(downgrade_targets()))
