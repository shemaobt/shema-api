from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.book_context import BCDGenerationLog
from app.models.book_context import ParticipantEntityType, ParticipantType
from app.services.book_context.generation.llm import call_llm
from app.services.book_context.generation.schemas import ParticipantRegisterSchema
from app.services.book_context.generation.state import BCDGenerationState
from app.services.book_context.generation.types import BHSAEntity

logger = logging.getLogger(__name__)

BATCH_SIZE = 80

_VALID_PARTICIPANT_TYPES = {member.value for member in ParticipantType}
_VALID_PARTICIPANT_ENTITY_TYPES = {member.value for member in ParticipantEntityType}

PARTICIPANT_PROMPT = """\
You are a biblical scholar creating a participant register for {book_name}.

Structural outline of the book:
{outline}

BHSA linguistic data summary:
{bhsa_summary}

## Person Entities (AUTHORITATIVE — pre-classified from BHSA)

The following entities have been classified as persons/groups by the BHSA linguistic \
database (via the `nametype` feature). Each entity includes: name, english_gloss, \
entity_type, entry_verse, exit_verse, appears_in, and appearance_count.

{person_entities}

## Common Noun Candidates (AUTHORITATIVE — BHSA-extracted lemmas)

The following lemmas were extracted directly from the BHSA. They are the ONLY \
source from which common-noun participant groups/roles may be drawn. Each \
candidate includes: lemma (Hebrew), lemma_ascii, english_gloss, sp \
("subs" / "adjv" / "verb"), appearance_count, top_functions, first_appears, \
sample_appears_in.

This list is filtered to substantives (`sp == "subs"`) so only nominal \
candidates are eligible. Verbs and abstract substantives that do not denote \
human collective roles are processed by other sections of the document.

{common_nouns}

## Output Rules (BHSA-strict)

You MUST produce participant entries ONLY from the two sources below. You MUST \
NOT invent participants that lack a BHSA anchor (proper-noun entity or \
common-noun candidate). Your scholarly enrichment is restricted to the \
descriptive fields explicitly listed for each source (`role_in_book`, \
`relationships`, `what_audience_knows_at_entry`, `arc`, `status_at_end`, and \
`type`).

### Source A — Person Entities (proper nouns)
Create an entry for EACH person entity in the Person Entities list above. \
All entities have already been classified as persons — do not skip any.

For each participant:
- name: copy EXACTLY from the entity data
- english_gloss: copy from the entity data. If empty, provide the English \
translation of the Hebrew name.
- entity_type: copy EXACTLY from the entity data
- type:
  - "named" (DEFAULT) — for any individual proper noun, INCLUDING toponyms \
treated as quasi-named entities (regions, tribal lands, kingdoms). \
Examples of `named`: personal names AND topo­nyms like Judah, Moab, Israel, \
Persia when used as country/region references.
  - "group" — ONLY for proper-noun collectives that explicitly denote a \
plurality of people as a corporate party (e.g., "Israelites", "Moabites" \
as a people). DO NOT use for country/region toponyms.
  - "divine" — for God / YHWH / Almighty / Elohim and divine epithets.
  Source A NEVER uses "unnamed" or "role" — those values are reserved for \
Source B (common-noun candidates).
- entry_verse: copy EXACTLY from the entity data (do NOT change)
- exit_verse: copy EXACTLY from the entity data (do NOT change)
- appears_in: copy the ENTIRE appears_in list EXACTLY from the entity data
- appearance_count: copy EXACTLY from the entity data
- role_in_book: their narrative role (protagonist, antagonist, supporting, etc.)
- relationships: list of relationship descriptions
- what_audience_knows_at_entry: what the audience knows when they first appear
- arc: list of {{at: {{chapter, verse}}, state: "description"}} tracking their development
- status_at_end: their state at the book's conclusion

You MUST NOT invent proper-noun participants outside the entity list.

### Source B — Common Noun Groups, Roles, Officials, and Unnamed Individuals
For EACH candidate in the Common Noun Candidates list whose `sp == "subs"` \
and whose semantics denote either:

  (a) a HUMAN COLLECTIVE GROUP — a plural/corporate party narratively \
significant in the book (e.g., elders, women of the city, reapers, \
foreigners, nobles, witnesses, the seven sons), OR

  (b) an INSTITUTIONAL ROLE OR OFFICE — a categorial human title that \
identifies a position in the book's social/political/religious system \
(e.g., king, queen, prince, priest, prophet, judge, official, eunuch, \
governor, satrap, lord, foreman, kinsman-redeemer), OR

  (c) an UNNAMED INDIVIDUAL — a SINGLE human referenced only by a \
common-noun descriptor (e.g., "the man's servant", "a woman from \
Bethlehem", "the foreman of the reapers", "a certain prophet"). Use \
this category when the lemma stands for a single individual whose \
identity is narratively important but who is never named. DO NOT use \
this for collective groups (use group) or for recurring institutional \
positions (use role).

create a participant entry. Static fields below MUST be copied EXACTLY \
from the candidate (they are deterministic):
- name: the Hebrew lemma (the `lemma` field) — copy EXACTLY
- english_gloss: copy EXACTLY from the candidate's `english_gloss`
- entity_type: "person_common"
- type:
  - "group" for category (a) — collective groups
  - "role" for category (b) — institutional roles/offices
  - "unnamed" for category (c) — single anonymous individuals
  - "divine" for the divine common noun אלהים (god[s]) when it refers \
to the proper deity. In that case ALSO override entity_type to "person".
- entry_verse: copy EXACTLY from the candidate's `first_appears`
- exit_verse: null
- appears_in: copy EXACTLY from the candidate's `sample_appears_in`
- appearance_count: copy EXACTLY from the candidate's `appearance_count`
- role_in_book, relationships, what_audience_knows_at_entry, arc, status_at_end: \
your scholarly enrichment based on the narrative

You MUST skip generic kinship terms (אב "father", אם "mother", אח \
"brother", בן "son", בת "daughter") UNLESS the book uses them to form \
a distinct narrative group with a specific role (e.g., "the seven sons \
of X" as a corporate party, "the daughters of Y" as a legal-precedent \
group). Mere familial references that fit any biblical narrative do not \
warrant participant entries.

You MUST NOT invent participants outside the candidate list. Skip candidates \
whose semantics do not denote a human collective group, an institutional \
role, an unnamed individual, or the divine deity (objects, places, rituals, \
and abstract concepts go to other sections).
"""


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


def _normalize_participant_entry(entry: dict[str, Any]) -> dict[str, Any]:
    type_value = entry.get("type")
    if type_value not in _VALID_PARTICIPANT_TYPES:
        entry["_legacy_type"] = type_value
        entry["type"] = ParticipantType.NAMED.value
    entity_type_value = entry.get("entity_type")
    if entity_type_value not in _VALID_PARTICIPANT_ENTITY_TYPES:
        entry["_legacy_entity_type"] = entity_type_value
        entry["entity_type"] = ParticipantEntityType.PERSON.value
    return entry


def _parse_and_normalize_participants(raw: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(_strip_markdown_fences(raw))
    except (TypeError, ValueError):
        logger.warning("Fallback parser could not load LLM raw payload as JSON")
        return []
    if isinstance(payload, dict):
        items = payload.get("participants", [])
    elif isinstance(payload, list):
        items = payload
    else:
        return []
    return [_normalize_participant_entry(dict(entry)) for entry in items if isinstance(entry, dict)]


async def _generate_batch(
    entities: list[BHSAEntity],
    state: BCDGenerationState,
    outline_json: str,
    common_nouns_json: str,
) -> list[dict[str, Any]]:
    prompt = PARTICIPANT_PROMPT.format(
        book_name=state["book_name"],
        outline=outline_json,
        bhsa_summary=state.get("bhsa_summary", ""),
        person_entities=json.dumps(entities, indent=2),
        common_nouns=common_nouns_json,
    )
    if state.get("user_feedback"):
        prompt += (
            "\n\n## User Feedback (address these concerns in your output)\n"
            + state["user_feedback"]
        )
    try:
        result = await call_llm(prompt, output_schema=ParticipantRegisterSchema)
        return [p.model_dump() for p in result.participants]
    except (ValidationError, OutputParserException) as exc:
        logger.warning(
            "LLM emitted out-of-enum participant payload; falling back to raw parse: %s",
            exc,
        )
        raw = await call_llm(prompt, output_schema=None)
        return _parse_and_normalize_participants(raw)


async def generate_participants(
    state: BCDGenerationState,
    *,
    db: AsyncSession | None = None,
    log: BCDGenerationLog | None = None,
) -> dict[str, list[dict[str, Any]]]:
    bhsa_entities = state.get("bhsa_entities", [])
    person_entities = [e for e in bhsa_entities if e.get("entity_type") in ("person", "ambiguous")]
    common_nouns = [c for c in state.get("bhsa_common_nouns", []) if c.get("sp") == "subs"]
    common_nouns_json = json.dumps(common_nouns, indent=2, ensure_ascii=False)

    if len(person_entities) <= BATCH_SIZE:
        participants = await _generate_batch(
            person_entities,
            state,
            json.dumps(state.get("structural_outline", {}), indent=2),
            common_nouns_json,
        )
        return {"participant_register": participants}

    batches = [
        person_entities[i : i + BATCH_SIZE] for i in range(0, len(person_entities), BATCH_SIZE)
    ]
    logger.info(
        "Splitting %d entities into %d batches of ~%d",
        len(person_entities),
        len(batches),
        BATCH_SIZE,
    )

    outline_json = json.dumps(state.get("structural_outline", {}), indent=2)
    all_participants: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for idx, batch in enumerate(batches, 1):
        logger.info(
            "Processing participant batch %d/%d (%d entities)",
            idx,
            len(batches),
            len(batch),
        )
        if db and log:
            log.output_summary = f"Batch {idx}/{len(batches)} ({len(batch)} entities)"
            await db.commit()

        batch_result = await _generate_batch(batch, state, outline_json, common_nouns_json)
        for p in batch_result:
            name = p.get("name", "")
            if name not in seen_names:
                seen_names.add(name)
                all_participants.append(p)
            else:
                logger.warning("Skipping duplicate participant: %s", name)

    return {"participant_register": all_participants}
