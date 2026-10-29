r"""Marcia's `checkRound`, ported whole as pure functions over one round's result.

Read from `src/golden/bt.ts` in `shemaobt/Tripod-Internalization` on 2026-09-11. The rules are
hers and so are the failure messages, in her English, because a report of ours is read beside
one of hers and a rule renamed on our side is a rule the two stacks no longer share. No check
is added, none is dropped, none is loosened. Two came after that reading, both read from
`src/golden/btChecks.ts` at her freeze, 18fa7c4: `spoken_whole_sentence`, which she added on
2026-09-21 with the Ensaio Final, and the clean round of her ruling of 2026-09-24.

Her regexes carry JavaScript's `u` flag, which Python's `re` is always in, and her
`(?<!\p{L})…(?!\p{L})` boundaries have no `\p{L}` here. `\b` is the translation: it is
Unicode-aware in Python 3, so `\bvocê\b` does not match inside `vocês`, which is the whole
reason she could not use plain `\b` in JavaScript.

The two are not identical, and the difference was measured rather than assumed. JavaScript's
`\b` is ASCII-only, so an accented letter is a non-word character to it and a word character
to us; Python's counts digits and `_` as word characters where her `\p{L}` guards do not.
Every input that separates them, and which way:

    você2, 3você, _você, contou1   she fails the turn, we pass
    sertão mapa                    she says "says 'o mapa'", we pass: her `\b` breaks
                                   between "ã" and "o", ours does not
    frase 1º, frase 1ª             her `frase\s+1\b` is satisfied, ours is not: the ordinal
                                   indicator is a non-word character to her and a word
                                   character to us, so we report a frase she counts as named

None of them is a sentence a Portuguese Speaker turn produces, and everything that is comes
out the same on both sides.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from scripts.bt_golden_runner import Script

#: The commit of her repository whose `src/golden/btChecks.ts` these checks apply.
BT_CHECKS_PIN = "18fa7c4"

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
_A_PART_AGAIN = re.compile(
    r"grav\w+ (?:de novo )?(?:essa|a) parte|regrav\w+ (?:essa|a) (?:parte|cena)", re.IGNORECASE
)


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


def asks_the_whole_sentence(spoken: str, number: int) -> list[str]:
    asked = re.search(
        rf"regrav\w+[^.]*?\bfrase(?:\s+{number}\b|(?!\s+\d))[^.]*?\binteira"
        rf"|regrav\w+\s+inteira\s+a\s+frase|\bfrase\s+{number}\s+inteira"
        r"|a frase toda|nunca só um pedaço",
        spoken,
        re.IGNORECASE,
    )
    fails = []
    if not asked:
        fails.append(
            f'the voice does not ask to record frase {number} again WHOLE ("regravem a frase '
            f'{number} inteira" / "essa frase inteira" / "a frase toda")'
        )
    part = _A_PART_AGAIN.search(spoken)
    if part:
        fails.append(
            "the voice sends the team to a PART on a recording that can take a sentence: "
            f'"{part.group(0)}"'
        )
    return fails


def one_frase_per_turn(spoken: str) -> list[str]:
    named = list(dict.fromkeys(said.lower() for said in _A_FRASE.findall(spoken)))
    if len(named) <= 1:
        return []
    return [f"more than one frase named in one turn: {', '.join(named)}"]


class Told(NamedTuple):
    """What the team told up to a round, with the language the clean-round check reads."""

    language: str
    frases: tuple[str, ...]


def told_up_to(script: Script, idx: int) -> Told:
    """Every frase told up to and including round `idx`, superseded ones too."""
    return Told(
        script.language,
        tuple(one["text"] for round_ in script.rounds[: idx + 1] for one in round_.frases),
    )


#: The clean-round fixed line — punctuation-tolerant, the words exact.
CLEAN_LINE_RE = re.compile(
    r"no que vocês me traduziram,?\s*tem tudo o que a história conta"
    r"\s*[—\u2013,-]?\s*e nada a mais",
    re.IGNORECASE,
)

#: Words a clean verdict may say whatever the team told, compared by stem.
CLEAN_ALLOWED = " ".join(
    [
        "no que vocês me traduziram, tem tudo o que a história conta — e nada a mais",
        "ouvir tudo de novo, do começo ao fim, e aprovar como rascunho final — o último passo, "
        "a última etapa: escutem, ouçam, aprovem a gravação inteira, a tradução de vocês",
        "vocês fizeram um bom trabalho, ótimo, muito bem, parabéns, cuidado, obrigada, obrigado "
        "— que bom, estou muito contente, feliz, alegre, espero",
        "vocês chegaram até o fim, chegaram até aqui, chegamos ao fim desta passagem, a tradução "
        "chegou inteira — eu ouvi tudo, frase por frase — voltem ao começo, voltar ao começo",
        "a tradução ficou completa, certinha, certo, certa, nenhum detalhe, nenhuma, detalhes, "
        "se estiver tudo certo, com calma, no tempo de vocês — a passagem, as frases, a frase, a "
        "cena, as cenas, a parte, as partes, o áudio, as gravações, toquem na tela, no botão, "
        "tocar",
        "que com sem uma umas uns dos das nos nas ele ela eles elas dele dela deles delas nele "
        "nela seu sua seus suas meu minha nosso nossa lhe mim por pra pro para pela pelo pelos "
        "pelas aos num numa não sim mas até como mais muito muita muitos muitas todo toda todos "
        "todas nada isso isto esse essa esses essas este esta estes estas aqui ali então agora "
        "quando porque também ainda depois antes onde cada mesmo mesma outro outra entre sobre "
        "já bem bom boa",
        "tem têm teve foi foram era eram ser ter ver vai vão são está estão estava estavam tinha "
        "tinham tenho fez fazer faz pode podem vamos seja sejam deu dar ficou ficaram ficar vez",
    ]
)

_LETTERS = r"[^\W\d_]"
#: What the story keeps quiet, said any of the ways the voice has said it. Never "não conta".
QUIET_RE = re.compile(
    rf"sil[êe]nci{_LETTERS}*"
    rf"|(?<!{_LETTERS})(?:cal(?:a|am|ou|aram|ada|adas|ado|ados|ar)|quiet{_LETTERS}*"
    rf"|segredo{_LETTERS}*)(?!{_LETTERS})"
    r"|a história (?:cala|guarda|esconde|omite|deixa (?:de fora|em branco)"
    rf"|não (?:diz|fala|mostra|revela|explica))(?!{_LETTERS})",
    re.IGNORECASE,
)
#: A noun made from the team's own verb ("choro"/"choraram") shares under five letters with it.
_ROOT_END = re.compile(
    r"(?:mentos?|coes|cao|ancas?|encias?|idas?|adas?|idos?|ados?|os|as|es|o|a|e)$"
)


def _words(text: str) -> list[str]:
    plain = "".join(
        ch
        for ch in unicodedata.normalize("NFD", text)
        if not unicodedata.category(ch).startswith("M")
    )
    return [one for one in re.findall(f"{_LETTERS}+", plain.lower()) if len(one) >= 3]


def _stem(word: str) -> str:
    return word[:5]


_ALLOWED_STEMS = {_stem(one) for one in _words(CLEAN_ALLOWED)}


def clean_round_fails(spoken: str, told: Told) -> list[str]:
    """A round expected clean: her fixed line and no word of what the team told (2026-09-24)."""
    if not re.search("portugu", told.language, re.IGNORECASE):
        return [
            f'clean round: this check reads Portuguese only — "{told.language}" has no fixed '
            "line or allowed words in src/golden/btChecks.ts yet; add them before trusting "
            "this script's clean round"
        ]
    fails: list[str] = []
    if not CLEAN_LINE_RE.search(spoken):
        fails.append(
            'clean round: the voice does not say the fixed line ("no que vocês me traduziram, '
            'tem tudo o que a história conta — e nada a mais")'
        )
    told_words = [one for text in told.frases for one in _words(text)]
    told_stems = {_stem(one) for one in told_words}

    def tells_it(word: str) -> bool:
        if _stem(word) in told_stems:
            return True
        root = _ROOT_END.sub("", word, count=1)
        return root != word and len(root) >= 4 and any(one.startswith(root) for one in told_words)

    named = list(
        dict.fromkeys(
            one for one in _words(spoken) if _stem(one) not in _ALLOWED_STEMS and tells_it(one)
        )
    )
    if named:
        fails.append(
            "clean round: the voice recites the passage — it names what the team told: "
            f'{", ".join(named)} (Marcia\'s ruling 2026-09-24: only "tem tudo", no detail)'
        )
    quiet = QUIET_RE.search(spoken)
    if quiet:
        fails.append(
            f'clean round: the voice speaks of what the story keeps quiet: "{quiet.group(0)}"'
        )
    return fails


def check_round(
    result: dict[str, Any], expect: dict[str, Any], told: Told | None = None
) -> list[str]:
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
    if expect.get("spoken_whole_sentence") is not None:
        fails += asks_the_whole_sentence(spoken, expect["spoken_whole_sentence"])
    fails += one_frase_per_turn(spoken)
    if expect["conferida"] and not expect["findings"] and not findings:
        fails += (
            clean_round_fails(spoken, told)
            if told
            else ["clean round: no telling handed to the check — pass toldUpTo(script, i)"]
        )
    return fails
