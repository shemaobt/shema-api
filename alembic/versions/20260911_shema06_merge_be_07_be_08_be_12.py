"""merge be-07, be-08 and be-12: three revisions authored against the same head

Revision ID: 20260911_shema06
Revises: 20260911_shema03, 20260911_shema04, 20260911_shema05
Create Date: 2026-09-11

BE-07, BE-08 and BE-12 each branched from `20260911_shema02` (BE-06's revision) in the same
wave and each authored its own migration against that one head, per `docs/shema.md` §7.1 —
*the migration parent is read off the base at write time*, and none of the three had the
other two to read yet. All three minted the identical literal revision id
`20260911_shema03`, which BE-15 found on merging the three branches together: not the
ordinary multi-head fork the wave's collision rule anticipates, but a literal collision
`alembic` cannot resolve with `merge heads` until the ids differ.

**What BE-15 did about it, in this branch only.** BE-12's file kept its id —
`20260911_shema03_forms.py`, untouched, first in the declared merge order. BE-07's was
renumbered to `20260911_shema04` (`20260911_shema04_health_assessment_provenance.py`) and
BE-08's to `20260911_shema05` (`20260911_shema05_needs_lifecycle.py`). Each file's own
`down_revision` stays `20260911_shema02`, so the three remain siblings rather than a
re-pointed chain, and this revision is what joins them — the merge is empty on both sides
because each of the three already carries its own schema change; there is nothing left to
reconcile once all three have run.

This revision id is `20260911_shema06`, following this module's own naming rather than the
random hex `alembic merge heads` mints by default, so the sequence stays readable end to end.

Whoever merges BE-07's, BE-08's or BE-12's own PR into `dev` inherits a head that already
carries `20260911_shema03` (from BE-12, first in the declared merge order) — the renumbering
above is local to this branch, done so BE-15 could build and test against a single head, and
is named here so the person merging the three PRs upstream is not surprised by the id this
branch's own migration lands on top of.
"""

revision = "20260911_shema06"
down_revision = ("20260911_shema03", "20260911_shema04", "20260911_shema05")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
