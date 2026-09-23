from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.book_context import BCDGenerationLog
from app.models.book_context import PlaceType
from app.services.book_context.generation.llm import call_llm
from app.services.book_context.generation.nodes.utils import summarize_participants
from app.services.book_context.generation.schemas import (
    ContextSectionsBatchSchema,
    ContextSectionsSchema,
    PlacesRegisterSchema,
)
from app.services.book_context.generation.state import BCDGenerationState
from app.services.book_context.generation.types import BHSAEntity

logger = logging.getLogger(__name__)

PLACE_BATCH_SIZE = 60

_VALID_PLACE_TYPES = {member.value for member in PlaceType}


def _strip_markdown_fences(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)


def _normalize_place_entry(entry: dict[str, Any]) -> dict[str, Any]:
    type_value = entry.get("type")
    if type_value not in _VALID_PLACE_TYPES:
        entry["_legacy_type"] = type_value
        entry["type"] = PlaceType.OTHER.value
    return entry


def _parse_and_normalize_places(raw: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(_strip_markdown_fences(raw))
    except (TypeError, ValueError):
        logger.warning("Fallback parser could not load LLM place payload as JSON")
        return []
    if isinstance(payload, dict):
        items = payload.get("places", [])
    elif isinstance(payload, list):
        items = payload
    else:
        return []
    return [_normalize_place_entry(dict(entry)) for entry in items if isinstance(entry, dict)]


_EMPTY_CONTEXT_SECTIONS: dict[str, Any] = {
    "theological_spine": "",
    "places": [],
    "objects": [],
    "institutions": [],
    "genre_context": {},
    "maintenance_notes": {},
}


def _parse_and_normalize_context_sections(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(_strip_markdown_fences(raw))
    except (TypeError, ValueError):
        logger.warning("Fallback parser could not load LLM context_sections payload as JSON")
        return dict(_EMPTY_CONTEXT_SECTIONS)
    if not isinstance(payload, dict):
        return dict(_EMPTY_CONTEXT_SECTIONS)
    raw_places = payload.get("places", []) or []
    places = [
        _normalize_place_entry(dict(entry)) for entry in raw_places if isinstance(entry, dict)
    ]
    return {
        "theological_spine": payload.get("theological_spine", "") or "",
        "places": places,
        "objects": [o for o in (payload.get("objects") or []) if isinstance(o, dict)],
        "institutions": [i for i in (payload.get("institutions") or []) if isinstance(i, dict)],
        "genre_context": payload.get("genre_context") or {},
        "maintenance_notes": payload.get("maintenance_notes") or {},
    }


CONTEXT_SECTIONS_PROMPT = """\
You are a biblical scholar completing the Book Context Document for {book_name} ({genre}).

Structural outline:
{outline}

Participant register:
{participants}

Discourse threads:
{threads}

BHSA linguistic data summary:
{bhsa_summary}

## Place Entities (AUTHORITATIVE — pre-classified from BHSA)

The following entities have been classified as places by the BHSA linguistic \
database (via the `nametype` feature). Each entity includes: name, english_gloss, \
entity_type, entry_verse, exit_verse, appears_in, and appearance_count.

{place_entities}

## Common Noun Candidates (AUTHORITATIVE — BHSA-extracted lemmas)

The following lemmas were extracted directly from the BHSA. They are the ONLY \
source from which common-noun places, objects and institutions may be drawn. \
Each candidate includes: lemma, lemma_ascii, english_gloss, sp \
("subs"/"adjv"/"verb"), appearance_count, top_functions, top_binyans, \
first_appears, sample_appears_in.

{common_nouns}

## Output Rules (BHSA-strict)

You MUST produce common-noun places, objects and institutions ONLY by selecting \
candidates from the list above. You MUST NOT invent entries that lack a BHSA \
lemma anchor. Your scholarly enrichment is restricted to the descriptive fields \
explicitly listed for each task (e.g. `meaning_and_function`, `what_it_is`, \
`role_in_book`, `display_name`).

You MUST NOT include in `objects` or `institutions` any lemma that already \
appears in the participant register with `entity_type == "person_common"` \
(human collective groups, kinship categories, institutional roles/offices). \
Those belong only in the participant register; do not duplicate them here.

Generate the following sections:

1. **Theological Spine**: 2-4 paragraphs describing the theological arc of the book. \
How does God act? What theological themes run through the narrative? What is the book's \
contribution to the canon?

2. **Places**: Two sources.
(a) For EACH proper-noun place entity in the Place Entities list above, create an entry:
- name: copy EXACTLY from the entity data
- english_gloss: copy from the entity data. If empty, provide the English \
translation of the Hebrew name.
- entity_type: copy EXACTLY from the entity data ("place")
- first_appears: copy EXACTLY from the entity data (use entry_verse)
- type: city, region, field, country, etc. (your scholarly classification)
- meaning_and_function: the place's significance in the narrative (1-2 sentences)
- appears_in: copy the ENTIRE appears_in list EXACTLY from the entity data
- appearance_count: copy EXACTLY from the entity data
You MUST NOT invent proper-noun places outside the entity list.

(b) For EACH candidate in the Common Noun Candidates list whose `sp == "subs"` \
and whose semantics denote a NARRATIVE SETTING (field, gate, threshing floor, \
city wall, road, vineyard, etc.), create an entry:
- name: the Hebrew lemma (the `lemma` field) — copy EXACTLY
- english_gloss: copy EXACTLY from the candidate's `english_gloss`
- entity_type: "place_common"
- first_appears: copy EXACTLY from the candidate's `first_appears`
- appears_in: copy EXACTLY from the candidate's `sample_appears_in`
- appearance_count: copy EXACTLY from the candidate's `appearance_count`
- type: city / region / field / threshing_floor / gate / etc. (your scholarly \
classification of the lemma's semantic type)
- meaning_and_function: your scholarly enrichment in 1-2 sentences
You MUST NOT invent common-noun places outside the candidate list. Skip \
candidates whose semantics do not denote a narrative setting (those go to other \
sections).

3. **Objects**: For EACH candidate in the Common Noun Candidates list whose \
`sp == "subs"` and whose semantics fall into ONE of these classes, create \
an entry:

  (a) PHYSICAL OBJECT — ritual items, garments, tools, animals, monetary \
units, scrolls/letters, weapons, food and drink items, containers, \
agricultural products, body adornments
  (b) SYMBOLIC ITEM with narrative weight in the book (e.g., gallows as \
sign of judgment, sandal as legal exchange token, ashes as mourning sign)
  (c) NARRATIVE STATE OR CONDITION that recurs as a plot anchor \
(e.g., pregnancy/offspring when it drives the narrative, rest/security \
as a sought-after outcome, life as a recurring concern). Include this \
class ONLY when the lemma is referenced multiple times AND functions as \
a narrative thread, not when it is a passing abstraction.

For each entry:
- name: the Hebrew lemma (the `lemma` field) — copy EXACTLY
- display_name: A rich, narrative-faithful English name when scholarly \
tradition has one (e.g., a recurring ceremonial garment may be known by a \
canonical English label; a distinctive item central to the plot may have \
a culturally-known name in English biblical scholarship). Leave empty when \
the english_gloss is already self-explanatory and adding a label would be \
artificial.
- english_gloss: copy EXACTLY from the candidate's `english_gloss`
- first_appears: copy EXACTLY from the candidate's `first_appears`
- appears_in: copy EXACTLY from the candidate's `sample_appears_in`
- what_it_is: 1-2 sentences describing what the object/state is
- meaning_across_scenes: 2-3 sentences on how its role evolves in the narrative

Skip generic temporal markers (day, night, month, year) UNLESS they carry \
distinctive narrative or symbolic weight in this specific book. Skip body \
parts UNLESS they appear in a ritual or symbolic action central to the \
narrative. Skip purely theological abstractions (God's name, righteousness \
as a virtue, glory) — those belong in `theological_spine` or as \
institutions when they name a recognized structure. You MUST NOT invent \
objects outside the candidate list.

4. **Institutions**: For EACH candidate in the Common Noun Candidates list \
that denotes a CULTURAL, LEGAL, RELIGIOUS, OR CEREMONIAL STRUCTURE — NOT a \
human role/title (those go to participants as `type=role`). This includes:
  - Rituals and rites (e.g., feast, fast, festival, mourning rite, sealing)
  - Legal practices (e.g., redemption rights, gleaning rights, levirate \
marriage, decree, inheritance law)
  - Social structures as institutions (e.g., kinship clan as an institutional \
unit, kingship as an office, priesthood as an order)

Verbal lemmas (`sp == "verb"`) that name an institutional action (e.g., a \
verb of redemption, gleaning, sealing, fasting) are eligible. Substantive \
lemmas (`sp == "subs"`) naming the rite/concept itself are eligible. Skip \
candidates that are merely a human title or office (those belong in \
participants).

For each entry:
- name: the Hebrew lemma (the `lemma` field) — copy EXACTLY
- display_name: A rich, narrative-faithful English name in the form scholarly \
tradition uses (e.g., a culturally-recognized festival name, a legal-practice \
label, an institutional office name). The display_name should be readable to \
a Bible translator who does not read Hebrew (e.g., "Festival of Purim", \
"Kinsman-Redemption (Go'el)", "Levirate Marriage", "Persian Law / Irrevocable \
Decree"). Leave empty only when the english_gloss already serves as a \
recognized institutional name on its own.
- english_gloss: copy EXACTLY from the candidate's `english_gloss`
- first_invoked: copy EXACTLY from the candidate's `first_appears`
- appears_in: copy EXACTLY from the candidate's `sample_appears_in`
- what_it_is: 1-2 sentences describing the institution
- role_in_book: 1-2 sentences on its narrative function

You MUST NOT invent institutions outside the candidate list. Inferred \
institutions without a BHSA lemma anchor are NOT permitted.

5. **Genre Context**:
- primary_genre: The primary literary genre
- sub_genres: List of secondary genres present
- narrative_voice: Description of the narrative perspective
- temporal_setting: When the events take place
- audience_positioning: How the text positions the reader/listener

6. **Maintenance Notes**:
- generation_notes: Brief note about how this document was generated
- known_limitations: List of known limitations or areas that may need human review
"""

CONTEXT_NO_PLACES_PROMPT = """\
You are a biblical scholar completing the Book Context Document for {book_name} ({genre}).

Structural outline:
{outline}

Participant register:
{participants}

Discourse threads:
{threads}

BHSA linguistic data summary:
{bhsa_summary}

## Common Noun Candidates (AUTHORITATIVE — BHSA-extracted lemmas)

The following lemmas were extracted directly from the BHSA. They are the ONLY \
source from which common-noun places, objects and institutions may be drawn. \
Each candidate includes: lemma, lemma_ascii, english_gloss, sp \
("subs"/"adjv"/"verb"), appearance_count, top_functions, top_binyans, \
first_appears, sample_appears_in.

{common_nouns}

## Output Rules (BHSA-strict)

You MUST produce common-noun places, objects and institutions ONLY by selecting \
candidates from the list above. You MUST NOT invent entries that lack a BHSA \
lemma anchor. Your scholarly enrichment is restricted to the descriptive fields \
explicitly listed for each task (e.g. `meaning_and_function`, `what_it_is`, \
`role_in_book`, `display_name`).

You MUST NOT include in `objects` or `institutions` any lemma that already \
appears in the participant register with `entity_type == "person_common"` \
(human collective groups, kinship categories, institutional roles/offices). \
Those belong only in the participant register; do not duplicate them here.

Generate the following sections (proper-noun places are handled in a separate batch):

1. **Theological Spine**: 2-4 paragraphs describing the theological arc of the book. \
How does God act? What theological themes run through the narrative? What is the book's \
contribution to the canon?

2. **Common-Noun Places**: For EACH candidate in the Common Noun Candidates list \
whose `sp == "subs"` and whose semantics denote a NARRATIVE SETTING (field, gate, \
threshing floor, city wall, road, vineyard, etc.), create an entry:
- name: the Hebrew lemma (the `lemma` field) — copy EXACTLY
- english_gloss: copy EXACTLY from the candidate's `english_gloss`
- entity_type: "place_common"
- first_appears: copy EXACTLY from the candidate's `first_appears`
- appears_in: copy EXACTLY from the candidate's `sample_appears_in`
- appearance_count: copy EXACTLY from the candidate's `appearance_count`
- type: city / region / field / threshing_floor / gate / etc. (your scholarly \
classification of the lemma's semantic type)
- meaning_and_function: your scholarly enrichment in 1-2 sentences
You MUST NOT invent common-noun places outside the candidate list. Proper-noun \
places are emitted in a separate batch — do NOT include them here.

3. **Objects**: For EACH candidate in the Common Noun Candidates list whose \
`sp == "subs"` and whose semantics fall into ONE of these classes, create \
an entry:

  (a) PHYSICAL OBJECT — ritual items, garments, tools, animals, monetary \
units, scrolls/letters, weapons, food and drink items, containers, \
agricultural products, body adornments
  (b) SYMBOLIC ITEM with narrative weight in the book (e.g., gallows as \
sign of judgment, sandal as legal exchange token, ashes as mourning sign)
  (c) NARRATIVE STATE OR CONDITION that recurs as a plot anchor \
(e.g., pregnancy/offspring when it drives the narrative, rest/security \
as a sought-after outcome, life as a recurring concern). Include this \
class ONLY when the lemma is referenced multiple times AND functions as \
a narrative thread, not when it is a passing abstraction.

For each entry:
- name: the Hebrew lemma (the `lemma` field) — copy EXACTLY
- display_name: A rich, narrative-faithful English name when scholarly \
tradition has one (e.g., a recurring ceremonial garment may be known by a \
canonical English label; a distinctive item central to the plot may have \
a culturally-known name in English biblical scholarship). Leave empty when \
the english_gloss is already self-explanatory and adding a label would be \
artificial.
- english_gloss: copy EXACTLY from the candidate's `english_gloss`
- first_appears: copy EXACTLY from the candidate's `first_appears`
- appears_in: copy EXACTLY from the candidate's `sample_appears_in`
- what_it_is: 1-2 sentences describing what the object/state is
- meaning_across_scenes: 2-3 sentences on how its role evolves in the narrative

Skip generic temporal markers (day, night, month, year) UNLESS they carry \
distinctive narrative or symbolic weight in this specific book. Skip body \
parts UNLESS they appear in a ritual or symbolic action central to the \
narrative. Skip purely theological abstractions (God's name, righteousness \
as a virtue, glory) — those belong in `theological_spine` or as \
institutions when they name a recognized structure. You MUST NOT invent \
objects outside the candidate list.

4. **Institutions**: For EACH candidate in the Common Noun Candidates list \
that denotes a CULTURAL, LEGAL, RELIGIOUS, OR CEREMONIAL STRUCTURE — NOT a \
human role/title (those go to participants as `type=role`). This includes:
  - Rituals and rites (e.g., feast, fast, festival, mourning rite, sealing)
  - Legal practices (e.g., redemption rights, gleaning rights, levirate \
marriage, decree, inheritance law)
  - Social structures as institutions (e.g., kinship clan as an institutional \
unit, kingship as an office, priesthood as an order)

Verbal lemmas (`sp == "verb"`) that name an institutional action (e.g., a \
verb of redemption, gleaning, sealing, fasting) are eligible. Substantive \
lemmas (`sp == "subs"`) naming the rite/concept itself are eligible. Skip \
candidates that are merely a human title or office (those belong in \
participants).

For each entry:
- name: the Hebrew lemma (the `lemma` field) — copy EXACTLY
- display_name: A rich, narrative-faithful English name in the form scholarly \
tradition uses (e.g., a culturally-recognized festival name, a legal-practice \
label, an institutional office name). The display_name should be readable to \
a Bible translator who does not read Hebrew (e.g., "Festival of Purim", \
"Kinsman-Redemption (Go'el)", "Levirate Marriage", "Persian Law / Irrevocable \
Decree"). Leave empty only when the english_gloss already serves as a \
recognized institutional name on its own.
- english_gloss: copy EXACTLY from the candidate's `english_gloss`
- first_invoked: copy EXACTLY from the candidate's `first_appears`
- appears_in: copy EXACTLY from the candidate's `sample_appears_in`
- what_it_is: 1-2 sentences describing the institution
- role_in_book: 1-2 sentences on its narrative function

You MUST NOT invent institutions outside the candidate list. Inferred \
institutions without a BHSA lemma anchor are NOT permitted.

5. **Genre Context**:
- primary_genre: The primary literary genre
- sub_genres: List of secondary genres present
- narrative_voice: Description of the narrative perspective
- temporal_setting: When the events take place
- audience_positioning: How the text positions the reader/listener

6. **Maintenance Notes**:
- generation_notes: Brief note about how this document was generated
- known_limitations: List of known limitations or areas that may need human review
"""

PLACES_BATCH_PROMPT = """\
You are a biblical scholar creating place entries for {book_name}.

Create an entry for EACH place entity listed below. \
All entities have already been classified as places — do not skip any.

For each place:
- name: Copy EXACTLY from the entity data
- english_gloss: Copy from the entity data. If empty, provide the English \
translation of the Hebrew name.
- entity_type: Copy EXACTLY from the entity data
- first_appears: Copy EXACTLY from the entity data (use entry_verse)
- type: city, region, field, country, etc.
- meaning_and_function: The place's significance in the narrative
- appears_in: Copy the ENTIRE appears_in list EXACTLY from the entity data
- appearance_count: Copy EXACTLY from the entity data

CRITICAL: The name, english_gloss, entity_type, first_appears, appears_in, and \
appearance_count fields are static and MUST match the entity data exactly. \
Do NOT invent places not in the list.

## Place Entities

{place_entities}
"""


def _build_shared_context(state: BCDGenerationState) -> dict[str, str]:
    return {
        "book_name": state["book_name"],
        "genre": state["genre"],
        "outline": json.dumps(state.get("structural_outline", {}), indent=2),
        "participants": summarize_participants(state.get("participant_register", [])),
        "threads": json.dumps(state.get("discourse_threads", []), indent=2),
        "bhsa_summary": state.get("bhsa_summary", ""),
        "common_nouns": json.dumps(
            state.get("bhsa_common_nouns", []), indent=2, ensure_ascii=False
        ),
    }


async def _generate_place_batch(
    entities: list[BHSAEntity],
    book_name: str,
) -> list[dict[str, Any]]:
    prompt = PLACES_BATCH_PROMPT.format(
        book_name=book_name,
        place_entities=json.dumps(entities, indent=2),
    )
    try:
        result = await call_llm(prompt, output_schema=PlacesRegisterSchema)
        return [p.model_dump() for p in result.places]
    except (ValidationError, OutputParserException) as exc:
        logger.warning(
            "LLM emitted out-of-enum place payload; falling back to raw parse: %s",
            exc,
        )
        raw = await call_llm(prompt, output_schema=None)
        return _parse_and_normalize_places(raw)


async def generate_context_sections(
    state: BCDGenerationState,
    *,
    db: AsyncSession | None = None,
    log: BCDGenerationLog | None = None,
) -> dict[str, Any]:
    bhsa_entities = state.get("bhsa_entities", [])
    place_entities = [e for e in bhsa_entities if e.get("entity_type") == "place"]

    if len(place_entities) <= PLACE_BATCH_SIZE:
        ctx = _build_shared_context(state)
        prompt = CONTEXT_SECTIONS_PROMPT.format(
            **ctx,
            place_entities=json.dumps(place_entities, indent=2),
        )
        if state.get("user_feedback"):
            prompt += "\n\n## User Feedback (address these concerns)\n" + state["user_feedback"]
        try:
            result = await call_llm(prompt, output_schema=ContextSectionsSchema)
            return {
                "theological_spine": result.theological_spine,
                "places": [p.model_dump() for p in result.places],
                "objects": [o.model_dump() for o in result.objects],
                "institutions": [i.model_dump() for i in result.institutions],
                "genre_context": result.genre_context.model_dump(),
                "maintenance_notes": result.maintenance_notes.model_dump(),
            }
        except (ValidationError, OutputParserException) as exc:
            logger.warning(
                "LLM emitted invalid context_sections payload; falling back to raw parse: %s",
                exc,
            )
            raw = await call_llm(prompt, output_schema=None)
            return _parse_and_normalize_context_sections(raw)

    logger.info(
        "Splitting %d place entities into batches of ~%d",
        len(place_entities),
        PLACE_BATCH_SIZE,
    )

    ctx = _build_shared_context(state)
    no_places_prompt = CONTEXT_NO_PLACES_PROMPT.format(**ctx)
    if state.get("user_feedback"):
        no_places_prompt += (
            "\n\n## User Feedback (address these concerns)\n" + state["user_feedback"]
        )
    if db and log:
        log.output_summary = "Generating theology, objects, institutions..."
        await db.commit()

    try:
        sections_result = await call_llm(no_places_prompt, output_schema=ContextSectionsBatchSchema)
        sections_data: dict[str, Any] = {
            "theological_spine": sections_result.theological_spine,
            "places": [p.model_dump() for p in sections_result.places],
            "objects": [o.model_dump() for o in sections_result.objects],
            "institutions": [i.model_dump() for i in sections_result.institutions],
            "genre_context": sections_result.genre_context.model_dump(),
            "maintenance_notes": sections_result.maintenance_notes.model_dump(),
        }
    except (ValidationError, OutputParserException) as exc:
        logger.warning(
            "LLM emitted invalid context_sections_batch payload; falling back to raw parse: %s",
            exc,
        )
        raw = await call_llm(no_places_prompt, output_schema=None)
        sections_data = _parse_and_normalize_context_sections(raw)

    batches = [
        place_entities[i : i + PLACE_BATCH_SIZE]
        for i in range(0, len(place_entities), PLACE_BATCH_SIZE)
    ]
    all_places: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for idx, batch in enumerate(batches, 1):
        logger.info(
            "Processing place batch %d/%d (%d entities)",
            idx,
            len(batches),
            len(batch),
        )
        if db and log:
            log.output_summary = f"Places batch {idx}/{len(batches)} ({len(batch)} entities)"
            await db.commit()

        batch_result = await _generate_place_batch(batch, state["book_name"])
        for p in batch_result:
            name = p.get("name", "")
            if name not in seen_names:
                seen_names.add(name)
                all_places.append(p)

    for entry in sections_data.get("places", []):
        name = entry.get("name", "")
        if name and name not in seen_names:
            seen_names.add(name)
            all_places.append(entry)

    return {
        "theological_spine": sections_data.get("theological_spine", ""),
        "places": all_places,
        "objects": sections_data.get("objects", []),
        "institutions": sections_data.get("institutions", []),
        "genre_context": sections_data.get("genre_context", {}),
        "maintenance_notes": sections_data.get("maintenance_notes", {}),
    }
