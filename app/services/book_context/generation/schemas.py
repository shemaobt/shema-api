from pydantic import BaseModel, Field

from app.models.book_context import ArcEntry as ArcEntrySchema
from app.models.book_context import BCDInstitution as InstitutionSchema
from app.models.book_context import BCDObject as ObjectSchema
from app.models.book_context import BCDPlace as PlaceSchema
from app.models.book_context import EntryProvenance, ParticipantEntityType, ParticipantType
from app.models.book_context import EpisodeStatus as EpisodeStatusSchema
from app.models.book_context import GenreContext as GenreContextSchema
from app.models.book_context import MaintenanceNotes as MaintenanceNotesSchema
from app.models.book_context import StructuralOutline as StructuralOutlineSchema  # noqa: F401
from app.models.book_context import VerseRef as VerseRefSchema


class ParticipantSchema(BaseModel):
    name: str
    english_gloss: str = ""
    entity_type: ParticipantEntityType = ParticipantEntityType.PERSON
    type: ParticipantType = ParticipantType.NAMED
    entry_verse: VerseRefSchema
    exit_verse: VerseRefSchema | None = None
    appears_in: list[VerseRefSchema] = Field(default_factory=list)
    appearance_count: int = 0
    role_in_book: str = ""
    relationships: list[str] = Field(default_factory=list)
    what_audience_knows_at_entry: str = ""
    arc: list[ArcEntrySchema] = Field(default_factory=list)
    status_at_end: str = ""
    provenance: EntryProvenance = EntryProvenance.AI


class ParticipantRegisterSchema(BaseModel):
    participants: list[ParticipantSchema] = Field(default_factory=list)


class DiscourseThreadSchema(BaseModel):
    label: str
    opened_at: VerseRefSchema
    resolved_at: VerseRefSchema | None = None
    question: str
    status_by_episode: list[EpisodeStatusSchema] = Field(default_factory=list)
    provenance: EntryProvenance = EntryProvenance.AI


class DiscourseThreadsSchema(BaseModel):
    threads: list[DiscourseThreadSchema] = Field(default_factory=list)


class PlacesRegisterSchema(BaseModel):
    places: list[PlaceSchema] = Field(default_factory=list)


class ContextSectionsSchema(BaseModel):
    theological_spine: str = ""
    places: list[PlaceSchema] = Field(default_factory=list)
    objects: list[ObjectSchema] = Field(default_factory=list)
    institutions: list[InstitutionSchema] = Field(default_factory=list)
    genre_context: GenreContextSchema = Field(default_factory=GenreContextSchema)
    maintenance_notes: MaintenanceNotesSchema = Field(default_factory=MaintenanceNotesSchema)


class ContextSectionsBatchSchema(BaseModel):
    theological_spine: str = ""
    places: list[PlaceSchema] = Field(default_factory=list)
    objects: list[ObjectSchema] = Field(default_factory=list)
    institutions: list[InstitutionSchema] = Field(default_factory=list)
    genre_context: GenreContextSchema = Field(default_factory=GenreContextSchema)
    maintenance_notes: MaintenanceNotesSchema = Field(default_factory=MaintenanceNotesSchema)
