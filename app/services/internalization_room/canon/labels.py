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
from functools import lru_cache
from pathlib import Path

from app.models.internalization_room import CoverageLegend, LabelledElement
from app.services.internalization_room.canon.elements import Element, ElementKind, elements_for
from app.services.internalization_room.coverage import CoverageStatus

LABELS_DIR = Path(__file__).parent / "element-labels"

#: Equals, not a preference order. Within a passage that has a catalogue entry there is no
#: fallback language and no branch that reaches for one: a hole is refused, because the
#: alternative is an ALL_CAPS identifier or an English sentence in front of a facilitator who
#: does not read English.
LANGUAGES: tuple[str, ...] = ("pt", "en", "es")

#: What the pilot needs. Anything outside is refused rather than answered in the canon's
#: own English, which is the silent fallback this module exists to make impossible.
TRANSLATED_PERICOPES: frozenset[str] = frozenset({"P01", "P02", "P05", "P14"})

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
            **{
                f"label_{language}": _text(for_passage, pericope_num, element.key, language)
                for language in LANGUAGES
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

    **The declared limit, and it is not small.** This module promises that no preservation
    rule shows an ALL_CAPS technical key in any language, and that promise holds for a
    passage the catalogue has and for no other.

    Measured over the ten passages it does not have, 264 beads: six of the seven kinds carry
    the canon's `Hebrew / English` in `label_en` — 178 of 264 — and only `scene` comes
    through clean. Most of that is cosmetic: `נָעֳמִי / Naomi` **contains** the name a
    facilitator reads. The two that genuinely hurt are the two with no name in them at all:
    `preserved`, which is `KIND: note` and is ALL_CAPS in 18 of 18, and `absence`, which is a
    paragraph in 30 of 30.

    Refusing instead would take a whole session history down for one conversation, which is
    worse — so the gap is declared, and asserted in
    `tests/test_internalization_room_element_labels.py` so it cannot go stale in silence. It
    closes when a translator reaches those ten passages.
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


def _text(for_passage: dict, pericope_num: str, key: str, language: str) -> str:
    entry = for_passage.get(key)
    if entry is None:
        raise ElementLabelsBroken(f"{pericope_num} {key} has no label in any language")
    text = (entry.get(language) or "").strip()
    if not text:
        raise ElementLabelsBroken(f"{pericope_num} {key} has no {language} label")
    return text


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
