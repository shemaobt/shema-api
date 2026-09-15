from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.db.models.book_context import BCDStatus


class EntryProvenance(StrEnum):
    AI = "ai"
    AI_EDITED = "ai_edited"
    HUMAN = "human"


class ParticipantType(StrEnum):
    NAMED = "named"
    UNNAMED = "unnamed"
    GROUP = "group"
    DIVINE = "divine"
    ROLE = "role"


class ParticipantEntityType(StrEnum):
    PERSON = "person"
    PERSON_COMMON = "person_common"
    AMBIGUOUS = "ambiguous"


class PlaceType(StrEnum):
    CITY = "city"
    COUNTRY = "country"
    REGION = "region"
    DISTRICT = "district"
    EMPIRE = "empire"
    VILLAGE = "village"
    MOUNTAIN = "mountain"
    VALLEY = "valley"
    RIVER = "river"
    WELL = "well"
    FIELD = "field"
    ROAD = "road"
    GATE = "gate"
    TOWER = "tower"
    WALL = "wall"
    STRUCTURE = "structure"
    OTHER = "other"


class VerseRef(BaseModel):
    chapter: int
    verse: int


class ArcEntry(BaseModel):
    at: VerseRef
    state: str


class EpisodeStatus(BaseModel):
    at: VerseRef
    status: str


class BCDParticipantEntry(BaseModel):
    model_config = {"extra": "allow"}

    name: str
    english_gloss: str = ""
    entity_type: ParticipantEntityType = ParticipantEntityType.PERSON
    type: ParticipantType = ParticipantType.NAMED
    entry_verse: VerseRef
    exit_verse: VerseRef | None = None
    appears_in: list[VerseRef] = Field(default_factory=list)
    appearance_count: int = 0
    role_in_book: str
    relationships: list[str] = Field(default_factory=list)
    what_audience_knows_at_entry: str = ""
    arc: list[ArcEntry] = Field(default_factory=list)
    status_at_end: str = ""
    provenance: EntryProvenance = EntryProvenance.AI


class BCDDiscourseThread(BaseModel):
    model_config = {"extra": "allow"}

    label: str
    opened_at: VerseRef
    resolved_at: VerseRef | None = None
    question: str
    status_by_episode: list[EpisodeStatus] = Field(default_factory=list)
    is_resolved_at_entry: bool | None = None
    provenance: EntryProvenance = EntryProvenance.AI


class BCDPlace(BaseModel):
    model_config = {"extra": "allow"}

    name: str
    english_gloss: str = ""
    entity_type: str = "place"
    first_appears: VerseRef
    type: PlaceType = PlaceType.OTHER
    meaning_and_function: str = ""
    appears_in: list[VerseRef] = Field(default_factory=list)
    appearance_count: int = 0
    provenance: EntryProvenance = EntryProvenance.AI


class BCDObject(BaseModel):
    model_config = {"extra": "allow"}

    name: str
    display_name: str = ""
    english_gloss: str = ""
    first_appears: VerseRef
    what_it_is: str = ""
    meaning_across_scenes: str = ""
    appears_in: list[VerseRef] = Field(default_factory=list)
    provenance: EntryProvenance = EntryProvenance.AI


class BCDInstitution(BaseModel):
    model_config = {"extra": "allow"}

    name: str
    display_name: str = ""
    english_gloss: str = ""
    first_invoked: VerseRef
    what_it_is: str = ""
    role_in_book: str = ""
    appears_in: list[VerseRef] = Field(default_factory=list)
    provenance: EntryProvenance = EntryProvenance.AI


class BCDCreateRequest(BaseModel):
    genre: str = Field(min_length=1, max_length=50)
    section_label: str | None = None
    section_range_start: int | None = None
    section_range_end: int | None = None


class BCDGenerateRequest(BaseModel):
    feedback: str | None = Field(None, max_length=2000)


class BCDSectionUpdateRequest(BaseModel):
    data: dict[str, Any] | str | list[dict[str, Any]]
    locale: str = "en"


class BCDApprovalResponse(BaseModel):
    id: str
    bcd_id: str
    user_id: str
    role_at_approval: str
    roles_at_approval: list[str] = []
    reviewer_locale: str | None = None
    approved_at: datetime

    model_config = {"from_attributes": True}


class BCDApprovalDetail(BaseModel):
    id: str
    user_id: str
    user_name: str
    avatar_url: str | None
    role_at_approval: str
    roles_at_approval: list[str]
    reviewer_locale: str | None = None
    approved_at: str | None


class BCDApprovalStatusResponse(BaseModel):
    approvals: list[BCDApprovalDetail]
    covered_specialties: list[str]
    missing_specialties: list[str]
    distinct_reviewers: int
    is_complete: bool
    has_english_review: bool = False


class BCDFeedbackCreate(BaseModel):
    section_key: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1)


class BCDFeedbackResponse(BaseModel):
    id: str
    bcd_id: str
    section_key: str
    author_id: str
    content: str
    resolved: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BCDListResponse(BaseModel):
    id: str
    book_id: str
    section_label: str | None
    version: int
    is_active: bool
    status: BCDStatus
    prepared_by: str
    locked_by: str | None = None
    locked_by_name: str | None = None
    locked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterOutline(BaseModel):
    model_config = {"extra": "allow"}

    chapter: int
    title: str
    summary: str
    key_events: list[str] = Field(default_factory=list)
    provenance: EntryProvenance = EntryProvenance.AI


class StructuralOutline(BaseModel):
    model_config = {"extra": "allow"}

    book_arc: str
    chapters: list[ChapterOutline] = Field(default_factory=list)
    literary_structure: str = ""


class GenreContext(BaseModel):
    model_config = {"extra": "allow"}

    primary_genre: str = ""
    sub_genres: list[str] = Field(default_factory=list)
    narrative_voice: str = ""
    temporal_setting: str = ""
    audience_positioning: str = ""


class MaintenanceNotes(BaseModel):
    model_config = {"extra": "allow"}

    generation_notes: str = ""
    known_limitations: list[str] = Field(default_factory=list)


class BCDResponse(BCDListResponse):
    section_range_start: int | None
    section_range_end: int | None
    structural_outline: StructuralOutline | None
    participant_register: list[BCDParticipantEntry] | None
    discourse_threads: list[BCDDiscourseThread] | None
    theological_spine: str | None
    places: list[BCDPlace] | None
    objects: list[BCDObject] | None
    institutions: list[BCDInstitution] | None
    genre_context: GenreContext | None
    maintenance_notes: MaintenanceNotes | None
    generation_metadata: dict[str, Any] | None
    translations: dict[str, Any] | None = None


class EstablishedItem(BaseModel):
    category: str
    name: str
    english_gloss: str = ""
    description: str
    verse_reference: str


class PassageEntryBriefResponse(BaseModel):
    participants: list[BCDParticipantEntry]
    active_threads: list[BCDDiscourseThread]
    places: list[BCDPlace]
    objects: list[BCDObject]
    institutions: list[BCDInstitution]
    established_items: list[EstablishedItem]
    is_first_pericope: bool
    bcd_version: int


class BCDGenerationLogResponse(BaseModel):
    id: str
    bcd_id: str
    step_name: str
    step_order: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    input_summary: str | None
    output_summary: str | None
    token_count: int | None
    error_detail: str | None

    model_config = {"from_attributes": True}


class StalenessCheckResponse(BaseModel):
    is_stale: bool
    current_version: int | None = None


class ValidationIssue(BaseModel):
    severity: str
    message: str
    section: str


class CancelGenerationResponse(BaseModel):
    deleted: bool
    book_id: str
