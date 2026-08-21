"""What a facilitator reads on a bead, in the three languages the Desk offers.

The labels are **not** in the canon and must not be moved there. `canon/vendor/` is pinned to
an upstream commit and is overwritten wholesale by `scripts/sync_internalization_canon.py
--sync`, so anything written inside it is deleted by the next sync without a word.

They are keyed by `(pericope_num, element_key)`, never by the key alone. Measured over the
pilot's four pericopes: of the keys appearing in more than one, sixteen carry different text
in each — `scene:N`, `absence:N` and `preserved:RN` are numbered within the passage, and
`place:PL2` names a different phrasing in P01 and P05.

A label is short new writing over the canon text, not a translation of it. `Element.label`
stays as it is: it is what the classifier prompts read, and repurposing it for the screen
would change what the model sees.

One entry is provisional. `P02 / being:B2` is the three dead men collectively, but the canon
keys it as Elimelech because `elements._label()` splits on the first `]]` and drops the first
of three links. Correcting that changes the key, and coverage is persisted under these keys —
so it is a data migration and it is Henok's decision. Until then the label is written by
sense, and `labelled_elements` refuses a catalogue entry the canon no longer has, which is
what makes the day it moves a loud failure rather than a silent orphan.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from app.models.internalization_room import CoverageLegend, LabelledElement
from app.services.internalization_room.canon.elements import Element, ElementKind, elements_for
from app.services.internalization_room.canon.parse_map import load_book
from app.services.internalization_room.coverage import CoverageStatus

LABELS_DIR = Path(__file__).parent / "element-labels"

#: Equals, not a preference order. Within a passage that has a catalogue entry there is no
#: fallback language and no branch that reaches for one: a hole is refused, because the
#: alternative is an ALL_CAPS identifier or an English sentence in front of a facilitator who
#: does not read English.
LANGUAGES: tuple[str, ...] = ("pt", "en", "es")

#: Coverage states named here before they exist in `CoverageStatus`. Empty, and that is the
#: resting state: a name belongs here only while its label is written and its enum value is
#: not, and it leaves the moment the enum catches up. `partially_engaged` was the one entry,
#: written for ENG-441 while that slice was still a sibling branch; ENG-449 is where the two
#: met, so it left here. The set stays because the next state will need the same window, and
#: because an *undeclared* extra is still refused — a catalogue that quietly accepts names
#: nobody reads is how it drifts from the enum.
PENDING_COVERAGE_STATUS: frozenset[str] = frozenset()


class ElementLabelsBroken(Exception):
    """A catalogue this repository ships is missing, malformed or holed.

    Deliberately not a `ValidationError`, which is answered 400 with its own message in the
    body: a file of ours being wrong is not the caller's request being wrong, and answering
    it that way sends somebody to debug their own code over our deploy — with `P01 scene:1`
    in front of them to do it with. It carries no handler for the same reason, so it is a
    500 and is logged as ours, which is what the house rule asks of an infrastructure
    failure.

    Asking for a pericope nobody has translated stays a `ValidationError`: that one really
    is about what was asked for. ENG-449 decided what its route answers, and the decision was
    **404** — the canon serves all fourteen of Ruth, so reaching P03 through the Desk's
    selector is a well-formed request for a representation this deploy cannot produce, and
    400 would blame the caller for our gap. What this split guarantees is that a route can
    tell that apart from a catalogue of ours being holed, which stays a 500.
    """


def labelled_elements(
    pericope_num: str, *, book: str = "Ruth", catalogue_dir: Path = LABELS_DIR
) -> list[LabelledElement]:
    """The passage's beads in bead order, each named in every language.

    A passage with a catalogue entry is answered from it, whole: a hole raises
    `ElementLabelsBroken` naming the pericope, the key and the language rather than being
    filled in. A passage without one is answered from the canon — see `_from_the_canon`.

    **Which passages are translated is asked of the catalogue and never listed here.** A list
    beside it would be the same fact written twice, and it could only drift in the direction
    that hurts: the day somebody writes a passage into `ruth.json` and forgets the list, the
    translation sits there unread while the canon answers, which is the silent fallback this
    module exists to prevent — and nothing anywhere would go red.

    `ValidationError` is left for the one refusal that is genuinely about the request: a
    pericope this book does not have, which `elements_for` raises from the canon.

    English is named on its own below and the other languages are spread, which is the shape of
    the rule rather than a concession to the type checker: it is the one language a bead cannot
    reach the screen without, and `_required` says so in a type instead of in prose. A fourth
    language still costs a field here and a catalogue entry, which is what `extra="forbid"` on
    the model is for. It is also evaluated first, which is why `_text` never meets an entry
    whose English is missing.
    """
    elements = elements_for(pericope_num, book)
    for_passage = _catalogue(catalogue_dir, book).get(pericope_num)
    if for_passage is None:
        return [_from_the_canon(element) for element in elements]

    served = {element.key for element in elements}
    orphans = sorted(set(for_passage) - served)
    if orphans:
        raise ElementLabelsBroken(
            f"{pericope_num} {', '.join(orphans)} is labelled but the canon does not serve it"
        )

    return [
        LabelledElement(
            key=element.key,
            kind=element.kind,
            scene=element.scene,
            label_en=_required(for_passage, pericope_num, element.key),
            **{
                f"label_{language}": _text(for_passage, pericope_num, element.key, language)
                for language in LANGUAGES
                if language != REQUIRED_LANGUAGE
            },
        )
        for element in elements
    ]


def _from_the_canon(element: Element) -> LabelledElement:
    """A bead of a passage nobody has translated, named as well as it can honestly be.

    Reached when the catalogue has no entry for this passage. English comes almost free from
    the canon — §7 says so — so `Element.label` is the English, and Portuguese and Spanish are
    **absent**. Filling them with the English would put a
    sentence a facilitator does not read in front of them under the name of their own
    language, which is the silent fallback this module exists to prevent; leaving them null
    is the Desk's own `CoverageLabels` shape and draws as a missing translation.

    **No passage of Ruth reaches here any more.** The catalogue carries all fourteen, so for
    this book the path below is unreachable in production and exists for a book nobody has
    written a catalogue for at all. `test_a_passage_the_catalogue_does_not_have_still_falls_
    back_to_the_canon` is what keeps it honest, against a catalogue with the passage removed.

    **What it cost while it was reachable**, kept because it is the argument for ever writing
    a label: measured over the ten passages the catalogue did not have, 264 beads, six of the
    seven kinds carried the canon's `Hebrew / English` in `label_en` — 178 of 264 — and only
    `scene` came through clean. Most of that was cosmetic, since `נָעֳמִי / Naomi` **contains**
    the name a facilitator reads. The two that hurt were the two with no name in them at all:
    `preserved`, which is `KIND: note` and was ALL_CAPS in 18 of 18, and `absence`, a paragraph
    in 30 of 30.

    The gap was declared rather than hidden, and it closed: a translator reached those ten. The
    sentence that promised it would close is gone rather than left beside the fact that it did,
    and the test it pointed at no longer asserts the limit — it asserts the fallback, which is
    a different claim about a different thing.

    Refusing instead of falling back would take a whole session history down for one
    conversation, which is why the path stays even with nothing in this book using it.
    """
    return LabelledElement(
        key=element.key,
        kind=element.kind,
        scene=element.scene,
        label_pt=None,
        label_en=element.label,
        label_es=None,
    )


def legend(*, catalogue_dir: Path = LABELS_DIR) -> CoverageLegend:
    """The coverage states and the element kinds, named once rather than on every bead.

    Checked against the enums themselves, so a state or a kind added anywhere in the room
    cannot reach a screen without a name.
    """
    named = _legend(catalogue_dir)
    coverage_status = _named_group(
        named,
        "coverage_status",
        [s.value for s in CoverageStatus],
        pending=PENDING_COVERAGE_STATUS,
    )
    element_kind = _named_group(named, "element_kind", [k.value for k in ElementKind])
    return CoverageLegend(coverage_status=coverage_status, element_kind=element_kind)


#: The language a bead cannot reach the screen without. The other two are translation work and
#: may legitimately be missing — `LabelledElement` types them `str | None` for exactly that —
#: so a catalogue entry written in English alone is an untranslated passage somebody finally
#: named, and not a holed file.
#:
#: Before this distinction existed the loader refused any empty language, which was the right
#: rule while only translated passages had entries at all. After ENG-442 it contradicted the
#: model it fills: adding the ten passages' English would have turned ten passages that
#: answered from the canon into `ElementLabelsBroken` — which carries no handler and is a 500.
REQUIRED_LANGUAGE = "en"


def _translated_into(for_passage: dict, language: str) -> bool:
    """Whether this passage has been translated into a language at all.

    The permission is for a passage nobody has translated, and the loader cannot tell that
    from a passage whose Spanish somebody deleted — unless it looks at the passage rather than
    at the bead. Written the other way round, blanking one label on a translated passage would
    have gone through in silence, which is the guarantee this module exists for.

    Today the data is exactly consistent: the pilot's four carry all three languages on every
    bead, and the ten carry English on every bead and nothing else on any. That is what makes
    a whole-passage rule the honest one — a passage is translated or it is not, and a bead is
    not a unit of translation.
    """
    return any((entry.get(language) or "").strip() for entry in for_passage.values())


def _required(for_passage: dict, pericope_num: str, key: str) -> str:
    """The label a bead cannot be served without. Absent, it is our own file being wrong.

    The check below is not unreachable, and a `pragma` saying so was wrong: `_text` refusing
    this language is the first guard and this is the second. Measured — a mutant removing
    either one alone survives the whole suite, and only removing both reddens
    `test_the_permission_does_not_reach_english`. Two guards for one rule is defence in depth
    rather than duplication, because the rule is what a bead cannot reach a screen without.
    """
    text = _text(for_passage, pericope_num, key, REQUIRED_LANGUAGE)
    if text is None:
        raise ElementLabelsBroken(f"{pericope_num} {key} has no {REQUIRED_LANGUAGE} label")
    return text


def _text(for_passage: dict, pericope_num: str, key: str, language: str) -> str | None:
    """One label, or nothing where nothing is a legitimate answer.

    Absent Portuguese is a passage waiting for a translator. Absent English is our own file
    being wrong — the difference between the two is the whole of the permission, and only one
    goes through.

    An entry empty in all three is caught by the English refusal above and never reaches the
    rest of this function: `labelled_elements` evaluates `label_en` before it spreads the other
    languages, so by the time this is asked about Portuguese the English of the same entry is
    known to be there. A separate refusal for "nothing in any language" was written here and
    measured dead — it promised a message that never came out.
    """
    entry = for_passage.get(key)
    if entry is None:
        raise ElementLabelsBroken(f"{pericope_num} {key} has no label in any language")
    text = (entry.get(language) or "").strip()
    if text:
        return text
    if language == REQUIRED_LANGUAGE:
        raise ElementLabelsBroken(f"{pericope_num} {key} has no {language} label")
    if _translated_into(for_passage, language):
        raise ElementLabelsBroken(
            f"{pericope_num} {key} has no {language} label, and the rest of the passage does"
        )
    return None


def _named_group(
    named: dict,
    group: str,
    values: list[str],
    *,
    pending: frozenset[str] = frozenset(),
) -> dict[str, dict[str, str]]:
    entries = named.get(group, {})
    extras = sorted(set(entries) - set(values) - pending)
    if extras:
        raise ElementLabelsBroken(
            f"{group} {', '.join(extras)} is named but is not a value of the enum"
        )
    resolved: dict[str, dict[str, str]] = {}
    for value in values:
        texts = entries.get(value)
        if texts is None:
            raise ElementLabelsBroken(f"{group} {value} has no name in any language")
        resolved[value] = {}
        for language in LANGUAGES:
            text = (texts.get(language) or "").strip()
            if not text:
                raise ElementLabelsBroken(f"{group} {value} has no {language} name")
            resolved[value][language] = text
    return resolved


@lru_cache(maxsize=8)
def _known_pericopes(book: str) -> frozenset[str]:
    """Which passages the canon has, asked once rather than by catching the refusal.

    `load_book` is `lru_cache`d and already parsed, so this costs a set comprehension over
    maps that are in memory either way.
    """
    return frozenset(meaning_map.pericope_num for meaning_map in load_book(book))


def label_index(
    pericope_nums: Iterable[str], *, book: str = "Ruth", catalogue_dir: Path = LABELS_DIR
) -> dict[tuple[str, str], LabelledElement]:
    """Every bead of the named passages, keyed by `(pericope_num, key)`.

    Built once for a page rather than per row. `labelled_elements` rebuilds its models on
    every call — the parsed catalogue is cached, the `LabelledElement` list is not — so
    resolving a fifty-card page one card at a time costs about 6.8 ms against 0.14 ms for
    this, and neither costs a trip to the database.

    **A passage the canon does not have is left out instead of raising.** The pericope is
    copied off the session, which the room app writes, and the key beside it arrives as an
    unvalidated form field: both are somebody else's input, and a lookup that raises on
    input turns one unreadable card into a facilitator with no inbox at all. A catalogue of
    ours that is holed still raises, through `labelled_elements` — that failure is ours and
    silence would bury it.
    """
    known = _known_pericopes(book)
    return {
        (pericope_num, element.key): element
        for pericope_num in {num for num in pericope_nums if num in known}
        for element in labelled_elements(pericope_num, book=book, catalogue_dir=catalogue_dir)
    }


@lru_cache(maxsize=8)
def _catalogue(catalogue_dir: Path, book: str) -> dict:
    return _read(catalogue_dir / f"{book.lower()}.json")


@lru_cache(maxsize=8)
def _legend(catalogue_dir: Path) -> dict:
    return _read(catalogue_dir / "legend.json")


def _read(path: Path) -> dict:
    """The catalogue as written, refused by name if it is not one.

    `json.loads` answers `Any`, so without this the shape is never established and the first
    symptom of a malformed file is an `AttributeError` raised somewhere far from it.
    """
    if not path.exists():
        raise ElementLabelsBroken(f"no label catalogue at {path}")
    written = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(written, dict):
        raise ElementLabelsBroken(f"{path.name} is not a catalogue of labels")
    return written
