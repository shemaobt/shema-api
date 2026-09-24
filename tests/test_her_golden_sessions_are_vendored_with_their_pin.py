"""Her five golden sessions are in this repo as bytes she wrote, at a commit we can name.

The runner plays her scripts; a copy that drifts from hers grades this room against its own
homework. So the scripts travel the same door as her doctrine and her prompts —
`scripts/sync_doctrine.py`, one pin, sha256 per file — and the expected digests here were
read off her checkout of `main` at the pinned commit, never off the vendored
copy.
"""

from __future__ import annotations

from scripts.sync_doctrine import REPO_ROOT, VENDORED, digest

HER_SESSIONS = {
    "J01-frame-before-elicit": "e23443e62451914a3df25246d93aea0eb056802693db3c8781c6c3f52f17fb6b",
    "P01-opening-and-mother-tongue": (
        "bfca62d7fc9d49e35a198a949e3cc5e9a0e0fbf4929a5421f9d32e49540bf641"
    ),
    "P01-retelling-gaps-and-additions": (
        "1afaa11b80a747c4fead63627757d60f489f34f66033c241fddc57aa99e68565"
    ),
    "P01-spoilers-and-boundaries": (
        "8901b50d7c9114218e1a7a0db7e23746c374dc62a4140bb6e9ffed2eaab9c70d"
    ),
    "P01-understand-first": "b9d88cdb283e69bc7d54ae5d38ee5a5a721903744c70b31281981e276570c905",
}


def test_her_five_session_scripts_are_vendored_byte_for_byte_under_the_pin() -> None:
    for name, hers in HER_SESSIONS.items():
        path = f"golden/sessions/{name}.json"
        assert VENDORED[path] == path, "her script keeps her path, so a diff against hers is a diff"
        assert digest((REPO_ROOT / path).read_bytes()) == hers, (
            f"{name}: the vendored bytes are not the ones on her branch at the pin"
        )


HER_REPORTS = {
    "README": "59e11392bcf254374f08f24114b2de7bfaec795e0326546a9bd0571946f001e1",
    "J01-frame-before-elicit": "c07028f01cd5feba3af745d833c22fc25d68eddba670a40651850b23eddc7163",
    "P01-opening-and-mother-tongue": (
        "773409f1f34261d48fad27818c5fe6ef622e4fa4dfb819c71d6879f896846e05"
    ),
    "P01-retelling-gaps-and-additions": (
        "695a209538e6ec90fab8292f0405b25da0b70bc1b464fc8dad601e979c1970c1"
    ),
    "P01-spoilers-and-boundaries": (
        "a7a1d985794fd3cd803d1a71da7bcce6ed5c1119c994249457ae57fa41d2f7e0"
    ),
    "P01-understand-first": "f4dc5df1d0e55cc69a6ec3fde78e320caa2071b8d432e258f4729de203b79c96",
}


def test_her_five_of_five_of_the_third_of_september_sits_beside_our_reports() -> None:
    for name, hers in HER_REPORTS.items():
        path = f"golden/reports/2026-09-03/{name}.md"
        assert VENDORED[path] == path, "her report dir keeps its date, beside the ones we write"
        assert digest((REPO_ROOT / path).read_bytes()) == hers, (
            f"{name}: the report is not the one her branch carries at the pin"
        )


def test_the_map_the_judge_is_handed_is_pinned_at_the_same_commit_on_both_stacks() -> None:
    hers = REPO_ROOT / VENDORED["VENDOR_PIN"]
    her_commit = next(
        line.split(":", 1)[1].strip()
        for line in hers.read_text(encoding="utf-8").splitlines()
        if line.startswith("pin_commit:")
    )
    ours = REPO_ROOT / "app/services/internalization_room/canon/vendor/VENDOR_PIN"

    assert ours.read_text(encoding="utf-8").strip() == her_commit, (
        "the two runs are only comparable when the vendored map comes from one compiler commit"
    )
