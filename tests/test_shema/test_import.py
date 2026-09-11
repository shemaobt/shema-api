"""What the Notion import promises, proved against rows shaped like the ones it refuses.

**The export itself is not here and must not be.** It is the whole dataset, it names
projects in sensitive countries, and the issue's last DoD line is that it stays out of the
repository — so every row below is synthetic and built by :func:`export_row`, and the real
127 are exercised by running the script, not by committing them into a fixture. What these
tests hold is the *rules*: the fail-closed flag, the refusals, the findings and the
idempotency, each of which can be shown on three records as well as on a hundred.

The one thing a synthetic row cannot prove is that the rules cover the real file, so
:func:`test_every_export_key_has_somewhere_to_go` proves it structurally instead: the union
of everything the reader maps, derives, refuses or deliberately drops **is** the export's 55
keys, so a key cannot be quietly ignored by being left out of a table.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaProjectStatus, ShemaRegionKey
from app.utils.shema_derivations import countries_named, country_of, region_of
from scripts.import_shema_projects import (
    DROPPED_KEYS,
    EXPORT_DATES,
    EXPORT_KEYS,
    HEALTH_DIMENSIONS,
    NOT_SENSITIVE,
    OWN_TABLE_KEYS,
    SENSITIVE,
    VERBATIM_INT,
    VERBATIM_LIST,
    VERBATIM_TEXT,
    Plan,
    SensitiveCountries,
    _report_destination,
    apply_plan,
    plan,
    to_export_date,
)


def export_row(**overrides: Any) -> dict[str, Any]:
    """One record with the export's 55 keys, filled the way the export fills most of them.

    The defaults are the export's own dominant values — every array empty, every health
    dimension ``""``, ``needsPastoralIntervention`` ``"nao"`` — so a test that overrides one
    key is testing that key alone.
    """
    row: dict[str, Any] = {
        "id": "afrikaans-kaaps",
        "languageName": "Afrikaans: Kaaps",
        "languageCode": "afr",
        "bridgeLanguage": "",
        "vitalityStatus": "",
        "location": "South Africa",
        "speakerCount": "",
        "coords": [25, -29],
        "translationType": [],
        "financialResources": [],
        "team": "YWAM Sydney",
        "ywamBase": "YWAM Sydney",
        "teamLeader": "",
        "mentor": "",
        "translators": "",
        "technicalReviewers": "",
        "partnerOrg": "",
        "teamContact": "Etienne Pieterse",
        "objective": ["Bíblia Completa"],
        "scopeDetails": "",
        "totalUnits": 1189,
        "totalUnitsType": "Capítulos",
        "translatedUnits": 0,
        "communityCheckedUnits": 0,
        "approvedUnits": 0,
        "startDate": "",
        "deadline": "",
        "status": "desconhecido",
        "sensitivity": "",
        "sensitiveCountry": False,
        "statusComments": "",
        "statusGoal": "Goal Met in the language",
        "orgRole": "",
        "phases": [],
        "materials": [],
        "storyProgress": [],
        "bookProgress": [],
        "progressHistory": [],
        "healthEmotional": "",
        "healthRelational": "",
        "healthSpiritual": "",
        "healthAssessmentDate": "",
        "healthAssessor": "",
        "healthNotes": "",
        "prayerRequests": "",
        "needsPastoralIntervention": "nao",
        "pastoralInterventionName": "",
        "needsItems": [],
        "needsNotes": "",
        "notes": "",
        "inETEN": False,
        "regionalCoordinator": "",
        "obtLabPerson": "",
        "resourceCirclePerson": "",
        "lastUpdated": "",
    }
    row.update(overrides)
    return row


def cleared(*countries: str) -> SensitiveCountries:
    """A client list that has answered *not sensitive* for exactly these countries."""
    return SensitiveCountries(
        dict.fromkeys(countries, NOT_SENSITIVE), source=Path("client-list.json")
    )


def only_record(built: Plan) -> Any:
    assert built.refusals == [], built.refusals
    assert len(built.records) == 1
    return built.records[0]


def test_every_export_key_has_somewhere_to_go() -> None:
    """No key of the export is ignored by omission — the tables together cover all 55.

    The failure this prevents is the quiet one: a key that is in no table is neither
    imported nor refused nor reported, and nothing says so. Adding a key to the export now
    fails here until somebody decides what it becomes.
    """
    handled = (
        {"id", "coords", "inETEN", "status", "needsPastoralIntervention", "sensitiveCountry"}
        | {"ywamBase"}
        | set(VERBATIM_TEXT)
        | set(VERBATIM_INT)
        | set(VERBATIM_LIST)
        | set(EXPORT_DATES)
        | set(HEALTH_DIMENSIONS)
        | set(OWN_TABLE_KEYS)
        | set(DROPPED_KEYS)
    )
    assert handled == set(EXPORT_KEYS)


class TestTheRegionIsDerivedFromTheFirstCountry:
    def test_the_export_spellings_are_the_keys(self) -> None:
        assert region_of("São Tomé e Príncipe") is ShemaRegionKey.AFRICA
        assert region_of("East Timor") is ShemaRegionKey.ASIA
        assert region_of("Papua New Guinea") is ShemaRegionKey.OCEANIA

    def test_several_countries_resolve_to_the_first(self) -> None:
        assert countries_named("China, Laos, Vietnam") == ("China", "Laos", "Vietnam")
        assert country_of("China, Laos, Vietnam") == "China"
        assert region_of("China, Laos, Vietnam") is ShemaRegionKey.ASIA

    def test_an_empty_location_lands_in_other_and_is_not_a_gap(self) -> None:
        assert countries_named("") == ()
        assert country_of("") == ""
        assert region_of("") is ShemaRegionKey.OTHER

    def test_a_country_the_map_does_not_name_lands_in_other(self) -> None:
        assert region_of("Laos") is ShemaRegionKey.OTHER

    def test_people_separators_never_split_a_place(self) -> None:
        """``&`` and ``/`` separate people in this export and never places."""
        assert countries_named("Pati & Marcos") == ("Pati & Marcos",)
        assert countries_named("Rodolfo / Debora") == ("Rodolfo / Debora",)


class TestDatesAreConvertedAtTheBoundary:
    def test_the_export_writes_day_first(self) -> None:
        assert to_export_date("13/04/2024", "x") == (date(2024, 4, 13), None)
        assert to_export_date("01/03/2022", "x") == (date(2022, 3, 1), None)

    def test_an_empty_date_is_null_and_not_a_refusal(self) -> None:
        assert to_export_date("", "x") == (None, None)

    def test_a_string_that_is_not_an_export_date_stops_the_run(self) -> None:
        """The frontend passes it through because its field is text; a date column cannot."""
        parsed, refusal = to_export_date("2024-04-13", "x")
        assert parsed is None
        assert refusal is not None

    def test_a_day_no_calendar_has_stops_the_run(self) -> None:
        """The reference implementation's range checks accept 31/02; a real date does not."""
        parsed, refusal = to_export_date("31/02/2024", "x")
        assert parsed is None
        assert refusal is not None

    def test_a_month_above_twelve_stops_the_run(self) -> None:
        assert to_export_date("13/13/2024", "x")[1] is not None


class TestTheFlagIsTheClientsAnswer:
    def test_with_no_list_every_record_is_sensitive(self) -> None:
        built = plan([export_row()], SensitiveCountries.pending())
        record = only_record(built)
        assert record.flag.sensitive is True
        assert record.values["sensitive_country"] is True

    def test_a_confirmed_country_clears_the_record(self) -> None:
        built = plan([export_row()], cleared("South Africa"))
        assert only_record(built).flag.sensitive is False

    def test_a_country_the_list_does_not_name_is_sensitive(self) -> None:
        built = plan([export_row(location="Sudan")], cleared("South Africa"))
        record = only_record(built)
        assert record.flag.sensitive is True
        assert any("unrecognised" in reason for reason in record.flag.reasons)

    def test_a_country_the_client_confirmed_sensitive_is_sensitive(self) -> None:
        countries = SensitiveCountries({"Egypt": SENSITIVE})
        built = plan([export_row(location="Egypt")], countries)
        record = only_record(built)
        assert record.flag.sensitive is True
        assert any("confirmed sensitive" in reason for reason in record.flag.reasons)

    def test_one_unanswered_country_flags_the_whole_record(self) -> None:
        """``China, Laos, Vietnam`` is one record and three questions."""
        built = plan([export_row(location="China, Laos, Vietnam")], cleared("China", "Laos"))
        record = only_record(built)
        assert record.flag.sensitive is True
        assert any(reason.startswith("Vietnam") for reason in record.flag.reasons)

    def test_an_empty_location_is_sensitive(self) -> None:
        built = plan([export_row(location="", coords=[0, 0])], cleared("South Africa"))
        assert only_record(built).flag.sensitive is True

    def test_the_export_may_raise_the_flag_over_a_cleared_country(self) -> None:
        """``zapoteco-de-santiago-lachirigi`` is Confidential in a country seven others are not."""
        built = plan(
            [export_row(location="Mexico", sensitivity="Confidential", sensitiveCountry=True)],
            cleared("Mexico"),
        )
        record = only_record(built)
        assert record.flag.sensitive is True

    def test_an_unrecognised_sensitivity_word_raises_the_flag(self) -> None:
        built = plan([export_row(sensitivity="Restricted-ish")], cleared("South Africa"))
        assert only_record(built).flag.sensitive is True

    def test_unrestricted_is_not_a_reason_to_flag(self) -> None:
        built = plan([export_row(sensitivity="Unrestricted")], cleared("South Africa"))
        assert only_record(built).flag.sensitive is False

    def test_a_verdict_the_file_cannot_state_is_refused(self, tmp_path: Path) -> None:
        """A typo that silently meant *not sensitive* is what this whole file guards."""
        path = tmp_path / "countries.json"
        path.write_text(json.dumps({"countries": {"Brazil": "no"}}), encoding="utf-8")
        with pytest.raises(SystemExit):
            SensitiveCountries.from_file(path)

    def test_a_file_without_a_countries_object_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "countries.json"
        path.write_text(json.dumps({"countries": ["Brazil"]}), encoding="utf-8")
        with pytest.raises(SystemExit):
            SensitiveCountries.from_file(path)

    def test_a_list_that_answers_is_not_pending(self, tmp_path: Path) -> None:
        path = tmp_path / "countries.json"
        path.write_text(
            json.dumps(
                {
                    "confirmed_on": "2026-09-11",
                    "confirmed_by": "the client",
                    "countries": {"Brazil": NOT_SENSITIVE, "Egypt": SENSITIVE},
                }
            ),
            encoding="utf-8",
        )
        countries = SensitiveCountries.from_file(path)
        assert countries.is_pending is False
        assert countries.verdict_for("Brazil") == NOT_SENSITIVE
        assert countries.verdict_for("Egypt") == SENSITIVE
        assert countries.verdict_for("Nepal") == SENSITIVE


class TestNothingIsCleanedInSilence:
    def test_a_record_whose_keys_are_not_the_exports_stops_the_run(self) -> None:
        row = export_row()
        row["somethingNew"] = ""
        built = plan([row], SensitiveCountries.pending())
        assert built.records == []
        assert "unexpected ['somethingNew']" in built.refusals[0].detail

    def test_a_missing_key_stops_the_run(self) -> None:
        row = export_row()
        del row["notes"]
        built = plan([row], SensitiveCountries.pending())
        assert built.records == []
        assert "missing ['notes']" in built.refusals[0].detail

    def test_a_duplicate_id_stops_the_run(self) -> None:
        built = plan([export_row(), export_row()], SensitiveCountries.pending())
        assert len(built.records) == 1
        assert "more than once" in built.refusals[0].detail

    def test_a_child_collection_with_rows_stops_the_run_rather_than_being_dropped(self) -> None:
        row = export_row(needsItems=[{"category": "financial"}])
        built = plan([row], SensitiveCountries.pending())
        assert built.records == []
        assert "writes no child rows" in built.refusals[0].detail

    def test_an_org_chart_name_stops_the_run(self) -> None:
        built = plan([export_row(regionalCoordinator="Someone")], SensitiveCountries.pending())
        assert built.records == []
        assert "org chart" in built.refusals[0].detail

    def test_team_and_ywam_base_disagreeing_stops_the_run(self) -> None:
        """BE-02 collapsed the two into one column, which only holds while they agree."""
        built = plan([export_row(ywamBase="YWAM Perth")], SensitiveCountries.pending())
        assert built.records == []
        assert "one concept in two columns" in built.refusals[0].detail

    def test_a_status_outside_the_eight_stops_the_run(self) -> None:
        built = plan([export_row(status="arquivado")], SensitiveCountries.pending())
        assert built.records == []
        assert "not one of the eight" in built.refusals[0].detail

    def test_text_longer_than_its_column_stops_the_run(self) -> None:
        """SQLite stores it and PostgreSQL refuses it, so the suite has to be the one that asks."""
        built = plan([export_row(languageName="x" * 201)], SensitiveCountries.pending())
        assert built.records == []
        assert "language_name holds 200" in built.refusals[0].detail

    def test_the_ambiguous_values_are_reported_and_still_imported(self) -> None:
        built = plan(
            [
                export_row(
                    id="jaminawa",
                    languageCode="jaa-b",
                    coords=[0, 0],
                    totalUnits=25,
                    translatedUnits=156,
                    objective=[],
                )
            ],
            cleared("South Africa"),
        )
        record = only_record(built)
        assert record.values["language_code"] == "jaa-b"
        assert record.values["translated_units"] == 156
        kinds = {finding.kind for finding in built.findings}
        assert "languageCode is not ISO-shaped" in kinds
        assert "coords are [0, 0]" in kinds
        assert "translated units exceed the scope" in kinds
        assert "objective is empty" in kinds

    def test_a_disagreement_with_the_exports_own_flag_is_reported(self) -> None:
        """Once the client has answered, a record whose flag moves is a row to check."""
        built = plan([export_row(location="Sudan")], cleared("South Africa"))
        kinds = {finding.kind for finding in built.findings}
        assert "the flag disagrees with the export" in kinds

    def test_the_columns_empty_on_every_record_are_counted(self) -> None:
        built = plan([export_row(), export_row(id="second")], SensitiveCountries.pending())
        assert "bridgeLanguage" in built.columns_empty_everywhere
        assert "languageName" not in built.columns_empty_everywhere

    def test_answered_no_and_answered_none_are_not_counted_as_empty(self) -> None:
        """``inETEN`` false and ``communityCheckedUnits`` zero are answers, not absences."""
        built = plan([export_row(), export_row(id="second")], SensitiveCountries.pending())
        assert "inETEN" not in built.columns_empty_everywhere
        assert "communityCheckedUnits" not in built.columns_empty_everywhere
        assert built.columns_false_everywhere == ("inETEN", "sensitiveCountry")
        assert built.columns_zero_everywhere == (
            "approvedUnits",
            "communityCheckedUnits",
            "translatedUnits",
        )

    def test_the_pending_list_does_not_report_the_disagreement_on_every_record(self) -> None:
        """127 identical lines would bury the rows a reviewer has to judge; §1 says it once."""
        pending = plan([export_row()], SensitiveCountries.pending())
        kinds = {finding.kind for finding in pending.findings}
        assert "the flag disagrees with the export" not in kinds


class TestNothingIsNormalised:
    def test_a_language_name_keeps_its_non_breaking_space(self) -> None:
        """Trimming or casing a language name renames a language."""
        name = "Embera\xa0Dobida"
        built = plan([export_row(languageName=name)], cleared("South Africa"))
        record = only_record(built)
        assert record.values["language_name"] == name
        kinds = {finding.kind for finding in built.findings}
        assert "languageName carries unusual whitespace" in kinds

    def test_a_language_code_is_checked_and_never_refused(self) -> None:
        for code in ("?", "N/A", "not iso language", "LLL", "Rop", ""):
            built = plan([export_row(languageCode=code)], cleared("South Africa"))
            assert only_record(built).values["language_code"] == code

    def test_the_export_row_is_kept_beside_the_parsed_values(self) -> None:
        row = export_row(startDate="13/04/2024", sensitivity="Confidential", sensitiveCountry=True)
        record = only_record(plan([row], cleared("South Africa")))
        assert record.values["start_date"] == date(2024, 4, 13)
        assert record.source["startDate"] == "13/04/2024"
        assert record.source["sensitiveCountry"] is True
        assert record.source["ywamBase"] == "YWAM Sydney"

    def test_an_unassessed_health_dimension_is_null_and_not_boa(self) -> None:
        record = only_record(plan([export_row()], cleared("South Africa")))
        assert record.values["health_emotional"] is None
        assert record.values["health_relational"] is None
        assert record.values["health_spiritual"] is None

    def test_the_approved_count_is_imported_as_it_stands_and_marked_unverified(self) -> None:
        record = only_record(
            plan([export_row(translatedUnits=156, approvedUnits=156)], cleared("South Africa"))
        )
        assert record.values["approved_units"] == 156
        assert record.values["approved_units_unverified"] is True


async def _import(
    db: AsyncSession,
    rows: list[dict[str, Any]],
    countries: SensitiveCountries,
    *,
    write: bool = True,
    allow_lowering: bool = False,
) -> Any:
    built = plan(rows, countries)
    assert built.refusals == [], built.refusals
    return await apply_plan(db, built, countries, write=write, allow_lowering=allow_lowering)


async def _stored(db: AsyncSession, project_id: str) -> ShemaProject:
    row = (await db.execute(select(ShemaProject).where(ShemaProject.id == project_id))).scalar_one()
    await db.refresh(row)
    return row


class TestTheRunIsIdempotentAndDryRunnable:
    async def test_a_dry_run_writes_nothing(self, db_session: AsyncSession) -> None:
        outcome = await _import(
            db_session, [export_row()], SensitiveCountries.pending(), write=False
        )
        assert len(outcome.inserted) == 1
        assert (await db_session.execute(select(ShemaProject))).scalars().all() == []

    async def test_the_slug_is_the_id_and_no_new_one_is_minted(
        self, db_session: AsyncSession
    ) -> None:
        await _import(db_session, [export_row()], SensitiveCountries.pending())
        stored = await _stored(db_session, "afrikaans-kaaps")
        assert stored.id == "afrikaans-kaaps"
        assert stored.region_key is ShemaRegionKey.AFRICA
        assert stored.status is ShemaProjectStatus.DESCONHECIDO
        assert stored.objective == ["Bíblia Completa"]
        assert stored.translation_type == []
        assert stored.location == "South Africa"

    async def test_running_twice_neither_duplicates_nor_changes_anything(
        self, db_session: AsyncSession
    ) -> None:
        rows = [export_row(), export_row(id="ticuna", location="Colombia, Peru")]
        await _import(db_session, rows, SensitiveCountries.pending())
        second = await _import(db_session, rows, SensitiveCountries.pending())
        assert second.inserted == []
        assert second.unchanged == 2
        assert len((await db_session.execute(select(ShemaProject))).scalars().all()) == 2

    async def test_the_clients_list_arriving_later_corrects_the_placeholder_flags(
        self, db_session: AsyncSession
    ) -> None:
        """The sequence the whole script is shaped around: import fail-closed, correct later."""
        rows = [export_row()]
        await _import(db_session, rows, SensitiveCountries.pending())
        assert (await _stored(db_session, "afrikaans-kaaps")).sensitive_country is True

        withheld = await _import(db_session, rows, cleared("South Africa"))
        assert len(withheld.flags_lowering_withheld) == 1
        assert withheld.flags_lowered == []
        assert (await _stored(db_session, "afrikaans-kaaps")).sensitive_country is True

        lowered = await _import(db_session, rows, cleared("South Africa"), allow_lowering=True)
        assert len(lowered.flags_lowered) == 1
        assert (await _stored(db_session, "afrikaans-kaaps")).sensitive_country is False

    async def test_a_flag_is_raised_without_asking_for_permission(
        self, db_session: AsyncSession
    ) -> None:
        """Raising protects and lowering exposes, so only one of the two needs a second gate."""
        rows = [export_row()]
        await _import(db_session, rows, cleared("South Africa"))
        assert (await _stored(db_session, "afrikaans-kaaps")).sensitive_country is False

        raised = await _import(db_session, rows, SensitiveCountries({"South Africa": SENSITIVE}))
        assert len(raised.flags_raised) == 1
        assert (await _stored(db_session, "afrikaans-kaaps")).sensitive_country is True

    async def test_a_field_edited_in_the_product_survives_a_second_run(
        self, db_session: AsyncSession
    ) -> None:
        """This is a one-time migration and not a Notion synchroniser."""
        rows = [export_row()]
        await _import(db_session, rows, cleared("South Africa"))
        stored = await _stored(db_session, "afrikaans-kaaps")
        stored.bridge_language = "Português"
        stored.notes = "typed by a coordinator"
        await db_session.commit()

        await _import(db_session, rows, cleared("South Africa"))
        again = await _stored(db_session, "afrikaans-kaaps")
        assert again.bridge_language == "Português"
        assert again.notes == "typed by a coordinator"

    async def test_a_record_born_in_the_product_is_never_touched(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(
            ShemaProject(
                id="afrikaans-kaaps",
                language_name="typed here, not imported",
                sensitive_country=True,
                region_key=ShemaRegionKey.OTHER,
            )
        )
        await db_session.commit()

        outcome = await _import(db_session, [export_row()], cleared("South Africa"))
        assert outcome.inserted == []
        assert len(outcome.left_alone) == 1
        stored = await _stored(db_session, "afrikaans-kaaps")
        assert stored.language_name == "typed here, not imported"
        assert stored.sensitive_country is True
        assert stored.source is None

    async def test_a_corrected_country_moves_the_flag_and_leaves_the_region_to_its_service(
        self, db_session: AsyncSession
    ) -> None:
        rows = [export_row()]
        await _import(db_session, rows, cleared("South Africa"))
        stored = await _stored(db_session, "afrikaans-kaaps")
        stored.location = "Nepal"
        await db_session.commit()

        outcome = await _import(db_session, rows, cleared("South Africa"))
        assert len(outcome.flags_raised) == 1
        assert any("edited" in change.detail for change in outcome.left_alone)
        again = await _stored(db_session, "afrikaans-kaaps")
        assert again.sensitive_country is True
        assert again.region_key is ShemaRegionKey.AFRICA


def test_the_report_may_not_be_written_inside_the_repository() -> None:
    """It names projects in sensitive countries, and ``.gitignore`` is somebody else's promise."""
    inside = Path(__file__).resolve().parents[2] / "import-report.md"
    with pytest.raises(SystemExit):
        _report_destination(inside)


def test_the_report_may_be_written_outside_the_repository(tmp_path: Path) -> None:
    assert _report_destination(tmp_path / "report.md") == (tmp_path / "report.md").resolve()
