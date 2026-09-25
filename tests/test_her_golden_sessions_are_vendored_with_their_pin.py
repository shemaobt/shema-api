"""Her golden sessions are in this repo as bytes she wrote, at a commit we can name.

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
    "P01-ensaio-da-cena": "a796d7629cc81baff207e6b136fafda5b23f8eeebf7a33775c8238e0ba713f93",
    "P01-ensaio-final-send-off-a-small-gap": (
        "2675052b25d719e9c9bddf532f8da859487f97cad884baf114d5d39be065e05e"
    ),
    "P01-ensaio-final-send-off-b-oral-scene": (
        "240261a26ba07dbd87ca29b03b1be2851956851c7a6a82478577ce6d51046a07"
    ),
    "P01-ensaio-final-send-off-c-late-rehearsal": (
        "2e61be97152eb688af633a19560993c1f980e4dcdde2191fcc045e028a2d6c25"
    ),
    "P01-part-opening-closing": "0b0c6978679f3bb47808ca671c9b479aa3b3e1c4672f61a2a8e0232575ffe0c9",
    "P01-question-is-not-a-shelter": (
        "f6a17de7847be6ee29efc6fdbe183fc859963bd9976f4c1e94de3bb4e1c185f1"
    ),
    "P01-small-gaps-choice": "d0e3a5fa32b26cbe75ffc45b13e40ae67bba2aa840605cc5a23c5de03848f99b",
    "P02-meaning-not-form": "9f80d3a87ea1b53cd5b3623833f6956ecad2296470b9ba686c9a8f36b7d8f1d0",
    "P03-accept-meaning-and-microphone": (
        "6ae9f7c84402361cd01985a41432dfbdd3f74fc576e2e55483101eafb76a6c03"
    ),
}


def test_the_sessions_folder_holds_exactly_the_scripts_pinned_here() -> None:
    # `scripts_to_play` globs the folder and `drift()` walks `VENDORED`; only this list ties
    # the two, so a script dropped in the folder would be played by a full run and pinned by
    # nothing.
    on_disk = sorted(p.stem for p in (REPO_ROOT / "golden/sessions").glob("*.json"))
    assert on_disk == sorted(HER_SESSIONS), "a session script on disk that no pin vouches for"


def test_every_session_script_of_hers_is_vendored_byte_for_byte_under_the_pin() -> None:
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
