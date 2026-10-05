"""Her five golden sessions are in this repo as bytes she wrote, at a commit we can name.

The runner plays her scripts; a copy that drifts from hers grades this room against its own
homework. So the scripts travel the same door as her doctrine and her prompts —
`scripts/sync_doctrine.py`, one pin, sha256 per file — and the expected digests here were
read off her checkout of `fia/pilot-2026-09` at the pinned commit, never off the vendored
copy.
"""

from __future__ import annotations

import argparse

from scripts.golden_runner import SESSIONS_DIR, scripts_to_play
from scripts.sync_doctrine import FROZEN, REPO_ROOT, VENDORED, digest

HER_SESSIONS = {
    "J01-frame-before-elicit": "cf3bd7509c7ba509bcfa44540af5b2bed64c05037be8ef0c5d98cec07c34c6fd",
    "P01-ensaio-da-cena": "9630015855451a2ef9baa9745ef106bcc7085894071158c805b73ee3ea94977a",
    "P01-ensaio-final-send-off-a-small-gap": (
        "05df21b793d07bdf0a2eb327cde24c31e7514f0f65258162c8639a2eb9beb7f3"
    ),
    "P01-ensaio-final-send-off-b-oral-scene": (
        "5b466968442a4564ba56f2d875bc824610adcc27660a60f17dc361faa1763964"
    ),
    "P01-ensaio-final-send-off-c-late-rehearsal": (
        "2a5648f3a3a5c0076a86da80f71c67cb74f1cdb7fb23e7b2544aa8f253362fbd"
    ),
    "P01-fia-moments": "6d7d404153c7bdc82f19a29948b0d840aa26e269da07792ede858567b407685f",
    "P01-opening-and-mother-tongue": (
        "5506ce03e91de7ed9dff69b7f9f82f1defae9a17bf323bda5291d36586f4c80c"
    ),
    "P01-part-opening-closing": "dec568ca086f684389a1aaab8efda245acdf7df1ff6df8e80076b224274fbb55",
    "P01-question-is-not-a-shelter": (
        "a485a59f9ef062809de4d6fc7bf43e50e94e86267de60af5872115d59620b583"
    ),
    "P01-retelling-gaps-and-additions": (
        "745dadd7479ec8ade28387d2b244daadd53cd0af22f96491fc037fc1c50f178d"
    ),
    "P01-small-gaps-choice": "51b92e808aea03039e1f9309cdc6d4022f84c7cabb49f676cc67ba70257082ec",
    "P01-spoilers-and-boundaries": (
        "8901b50d7c9114218e1a7a0db7e23746c374dc62a4140bb6e9ffed2eaab9c70d"
    ),
    "P01-understand-first": "17c4b1fccb5a335b3c0dbd795b532ffa054818539fac03acab50004a1e99cbf6",
    "P02-meaning-not-form": "3e610b7e4d7487e227e2373c1e966373da92ff599171f5fe4b87082236d4ede7",
    "P03-accept-meaning-and-microphone": (
        "dc7787354d45a67b79e689bd2b247ad31de5ee733e02abff338c2e5b7b4eb6d6"
    ),
    "P08-resting-place": "004d363cf87ab4d9ca78d21231c9518791dcf73d0afcfcb784e0d3e9abb639f3",
    "P09-threshing-floor-night": "123e5c3ca8878fe223ca245ce0a527948f8c3095a7fe876e508e07a3d8e29301",
    "P10-earlier-passages-status": (
        "25aeb396375594eb1f5f94c9131eb62e696543d940b5022a45b9ad6a038f9f11"
    ),
    "P10-sit-still": "8182f9280b76494d17f32c4ff0583627812c1e54c7e0e1dc2e6900b3a33abd2e",
    "P11-the-gate": "3410b3784d5466e96de8ba932cf58c4227339bd7456e080aa75bb78b8e5940d1",
    "P12-the-blessing": "a14f2b774797db3a197a668c00e0e40e9eb08d792cafde61d41c0c31e8196c23",
    "P13-the-son": "9eaadd4231604c51218d16167c6efbce12d53faab22b0a0f2bb70734215164b6",
    "P14-the-generations": "01d374990dd376cf6ef86ffca1d8dc13a1437102d56b4937ed912280bac0c991",
}

HER_BT_SCRIPTS = {
    "P01-frases": "21b6a07e60ffdb85ced4caa360636f08a27bf46a0a30a2340250c75617f24439",
    "P01-regravar-frase-acrescimo": (
        "e88ce60380ad1e2a797207284987a12010528f57af55073cc78ed8c6cb17e2b5"
    ),
    "P01-regravar-frase-faltou": "09c84b62c76602aa25bcc8bc6f74e83eb0b6c8a632c6ede79a998d8b9db1c538",
    "P02-agentes-trocados": "6a5bfe682476a4f137132ccdb3a91c39a803126acbdcf0335c1ab6691f7832d2",
    "P02-bondade-fiel": "c32593844a9c6db21567d30afdc856344da497cfac0b7686f65ce5a4bf7f6987",
    "P02-causa-a-mais": "3755b9ee741db1551bf235ff5e10db5026761298e50a5872c16121684263f8fa",
    "P02-causa-trocada": "868c146a229d5a29d377f334dd7309b1ee91a3e4f698442b0c114350606602e4",
    "P02-nuance-espera": "d2e08f962a686eab31fc5273f425a1bf2615432fdbd07ad4a0cc6a6c0095219d",
    "P02-nuance-esta-noite": "6705c2665782a71c3fc42953127e48ce9a42ab67090f3b2de83da2019f8ce694",
    "P02-regravar-frase-troca": "2b30a932df7d5fcc944058530467ad8798ab0b25cb2c97827f7f5d18a21369de",
}


def test_her_twenty_three_session_scripts_are_vendored_byte_for_byte_at_the_freeze() -> None:
    for name, hers in HER_SESSIONS.items():
        path = f"golden/sessions/{name}.json"
        assert FROZEN[path] == path, "o roteiro dela guarda o caminho dela, então um diff é um diff"
        assert digest((REPO_ROOT / path).read_bytes()) == hers, (
            f"{name}: os bytes não são os do app congelado dela em 18fa7c4"
        )


def test_her_ten_bt_scripts_are_vendored_byte_for_byte_at_the_freeze() -> None:
    for name, hers in HER_BT_SCRIPTS.items():
        path = f"golden/bt/{name}.json"
        assert FROZEN[path] == path, "o roteiro bt dela guarda o caminho dela"
        assert digest((REPO_ROOT / path).read_bytes()) == hers, (
            f"{name}: os bytes não são os do app congelado dela em 18fa7c4"
        )


def test_the_runner_finds_her_twenty_three_sessions_where_it_looks_by_default() -> None:
    args = argparse.Namespace(script=None, sessions=SESSIONS_DIR, only=None)

    found = sorted(path.stem for path in scripts_to_play(args))

    assert found == sorted(HER_SESSIONS), "o runner jogava só os cinco roteiros de 533b6e3"


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
    hers = REPO_ROOT / FROZEN["VENDOR_PIN"]
    her_commit = next(
        line.split(":", 1)[1].strip()
        for line in hers.read_text(encoding="utf-8").splitlines()
        if line.startswith("pin_commit:")
    )
    ours = REPO_ROOT / "app/services/internalization_room/canon/vendor/VENDOR_PIN"

    assert ours.read_text(encoding="utf-8").strip() == her_commit, (
        "the two runs are only comparable when the vendored map comes from one compiler commit"
    )
