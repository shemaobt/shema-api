r"""Marcia's `checkRound`, ported whole as pure functions over one round's result.

Read from `src/golden/bt.ts` in `shemaobt/Tripod-Internalization` on 2026-09-11. The rules are
hers and so are the failure messages, in her English, because a report of ours is read beside
one of hers and a rule renamed on our side is a rule the two stacks no longer share. No check
is added, none is dropped, none is loosened.

Her regexes carry JavaScript's `u` flag, which Python's `re` is always in, and her
`(?<!\p{L})…(?!\p{L})` boundaries have no `\p{L}` here. `\b` is the translation: it is
Unicode-aware in Python 3, so `\bvocê\b` does not match inside `vocês`, which is the whole
reason she could not use plain `\b` in JavaScript.

The two are not identical, and the difference was measured rather than assumed. Python's `\b`
counts digits and `_` as word characters, and her bare `\bo mapa\b` counts accented letters as
non-word. Every input that separates them:

    você2, 3você, _você, contou1   she fails the turn, we pass
    sertão mapa                     she passes, we say "says 'o mapa'"

None of them is a sentence a Portuguese Speaker turn produces, and everything that is comes
out the same on both sides.
"""

from __future__ import annotations

import re
from typing import Any

#: Her unconditional checks, in the order `checkRound` applies them.
_SINGULAR = re.compile(r"\b(?:você|teu|tua|teus|tuas)\b", re.IGNORECASE)
_SINGULAR_SENTENCE = re.compile(r"\b(?:você|teu|tua|teus|tuas)\b[^.]*", re.IGNORECASE)
_PLURAL = re.compile(r"vocês", re.IGNORECASE)
#: Spec §5's vocabulary ruling: the word is traduzir/tradução. Bare `conta` stays — "isso a
#: história não conta" is the ruled frame.
_BANNED = re.compile(
    r"cont(?:ou|aram|em|a|ar) de volta|\b(?:contaram|contou|explicaram|descreveram)\b",
    re.IGNORECASE,
)
_TRADU = re.compile(r"tradu", re.IGNORECASE)
_THE_MAP = re.compile(r"\bo mapa\b", re.IGNORECASE)
_BLESSING = re.compile(r"vão com deus|deus (?:os|te) abençoe|amém", re.IGNORECASE)
_A_FRASE = re.compile(r"frase\s+\d+", re.IGNORECASE)


def _js(flag: bool) -> str:
    """A boolean spelled the way her report spells it."""
    return "true" if flag else "false"


def _notes(findings: list[dict[str, Any]]) -> str:
    return " | ".join(
        f"{one['kind']}{'' if one.get('frase') is None else '@' + str(one['frase'])}: {one['note']}"
        for one in findings
    )


def expected_findings(findings: list[dict[str, Any]], wanted: list[dict[str, Any]]) -> list[str]:
    """Each planted finding appeared, with the frase it was promised on where she named one.

    The hit is the *first* finding of that kind whose note matches, and the frase is checked
    on the hit alone: her scripts plant one thing per kind, and a second finding of the same
    kind is not the one the case is about.
    """
    fails: list[str] = []
    for want in wanted:
        hit = next(
            (
                one
                for one in findings
                if one["kind"] == want["kind"]
                and re.search(want["note"], one["note"], re.IGNORECASE)
            ),
            None,
        )
        if hit is None:
            fails.append(
                f"expected a {want['kind']} finding matching /{want['note']}/ — "
                f"got [{_notes(findings)}]"
            )
        elif want.get("frase") is not None and hit.get("frase") != want["frase"]:
            fails.append(
                f"the {want['kind']} finding should name frase {want['frase']}, "
                f"names {hit.get('frase') if hit.get('frase') is not None else 'none'}"
            )
    return fails


def no_finding(findings: list[dict[str, Any]], pattern: str) -> list[str]:
    """No note is about a detail the telling does carry, split across two frases."""
    return [
        f'a finding about a detail that IS in the telling (split across frases): "{one["note"]}"'
        for one in findings
        if re.search(pattern, one["note"], re.IGNORECASE)
    ]


def no_kinds(findings: list[dict[str, Any]], kinds: list[str]) -> list[str]:
    """A kind that must not appear at all — `["missing"]` where nothing is missing."""
    return [
        f'a {one["kind"]} finding must not appear here (no_kinds): "{one["note"]}"'
        for one in findings
        if one["kind"] in kinds
    ]


def no_findings_at_all(findings: list[dict[str, Any]], wanted: list[dict[str, Any]]) -> list[str]:
    if wanted or not findings:
        return []
    return [f"expected no findings, got [{_notes(findings)}]"]


def conferida(reached: bool, expected: bool, outcome: str) -> list[str]:
    if reached == expected:
        return []
    return [f"conferida={_js(reached)}, expected {_js(expected)} (outcome {outcome})"]


def fail_safe(outcome: str) -> list[str]:
    return ["the verdict fell to a fail-safe line"] if outcome == "fail_safe" else []


def singular_address(spoken: str) -> list[str]:
    if not _SINGULAR.search(spoken):
        return []
    said = _SINGULAR_SENTENCE.search(spoken)
    return [f'the voice addresses one person: "{said.group(0) if said else ""}"']


def says_voces(spoken: str) -> list[str]:
    return [] if _PLURAL.search(spoken) else ["the voice never says 'vocês'"]


def banned_vocabulary(spoken: str) -> list[str]:
    said = _BANNED.search(spoken)
    if said is None:
        return []
    return [f'banned vocabulary (spec §5 — the word is traduzir): "{said.group(0)}"']


def says_tradu(spoken: str) -> list[str]:
    return [] if _TRADU.search(spoken) else ["the voice never says traduzir/tradução"]


def o_mapa(spoken: str) -> list[str]:
    return ["says 'o mapa'"] if _THE_MAP.search(spoken) else []


def blessing(spoken: str) -> list[str]:
    return ["a blessing"] if _BLESSING.search(spoken) else []


def names_frase(spoken: str, number: int) -> list[str]:
    if re.search(rf"frase\s+{number}\b", spoken, re.IGNORECASE):
        return []
    return [f"the voice does not name frase {number}"]


def spoken_matches(spoken: str, pattern: str) -> list[str]:
    if re.search(pattern, spoken, re.IGNORECASE):
        return []
    return [f"the voice does not match /{pattern}/"]


def spoken_must_not_match(spoken: str, pattern: str) -> list[str]:
    """The marked silence the voice must never fill, quoted back with what it said."""
    said = re.search(pattern, spoken, re.IGNORECASE)
    if said is None:
        return []
    return [f'the voice must not match /{pattern}/ — it said: "{said.group(0)}"']


def asks_translation(spoken: str) -> list[str]:
    """Marcia's ruling 2026-09-06: the question is *na tradução*, never *na explicação*."""
    if _TRADU.search(spoken):
        return []
    return ["the voice does not ask whether it entered in the translation ('na tradução')"]


def one_frase_per_turn(spoken: str) -> list[str]:
    named = list(dict.fromkeys(said.lower() for said in _A_FRASE.findall(spoken)))
    if len(named) <= 1:
        return []
    return [f"more than one frase named in one turn: {', '.join(named)}"]


def check_round(result: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    """Every failure of one round, in her words and in her order.

    A key is applied only where her script carries it. That is what keeps her documented
    deviation intact: she removed `no_finding` from `P02-causa-a-mais` rather than loosening
    it, because that check sweeps every note and the addition's note rightly names the bread
    news as the contrast. A port that applied it anyway would fail a correct run.
    """
    findings = list(result["findings"])
    spoken = result["spoken"]
    fails = expected_findings(findings, expect["findings"])
    if expect.get("no_finding"):
        fails += no_finding(findings, expect["no_finding"])
    if expect.get("no_kinds"):
        fails += no_kinds(findings, expect["no_kinds"])
    fails += no_findings_at_all(findings, expect["findings"])
    fails += conferida(result["conferida"], expect["conferida"], result["outcome"])
    fails += fail_safe(result["outcome"])
    fails += singular_address(spoken)
    fails += says_voces(spoken)
    fails += banned_vocabulary(spoken)
    fails += says_tradu(spoken)
    fails += o_mapa(spoken)
    fails += blessing(spoken)
    if expect.get("spoken_names_frase") is not None:
        fails += names_frase(spoken, expect["spoken_names_frase"])
    if expect.get("spoken_matches"):
        fails += spoken_matches(spoken, expect["spoken_matches"])
    if expect.get("spoken_must_not_match"):
        fails += spoken_must_not_match(spoken, expect["spoken_must_not_match"])
    if expect.get("spoken_asks_audio_or_explanation"):
        fails += asks_translation(spoken)
    fails += one_frase_per_turn(spoken)
    return fails
