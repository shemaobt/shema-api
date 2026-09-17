"""The ownership rules of the people tables, checked by a glob rather than by review.

``docs/shema.md`` §6.4 gives its three privacy owners the same shape and the same argument:
each is the sole reader of what it guards, because *a rule applied per endpoint is a rule the
next endpoint forgets*. Sole ownership is only a claim until something fails on the second
reader, and this repository already has the mechanism —
``tests/test_resource_requests/test_access.py::test_the_app_key_is_named_once_in_the_module``
globs a directory and fails on a literal. This is that test, over a table instead of a string.

Nothing here needs a database, which is the point: these are the checks that keep passing
after somebody refactors the service that the behaviour tests exercise.
"""

from __future__ import annotations

from pathlib import Path

from app.db.models.shema_consent import ShemaConsentContext
from app.db.models.shema_intercessor import ShemaIntercessor
from app.db.models.shema_org_chart import ShemaRegionTeam
from app.services.shema._directory import leaving_person
from app.utils.shema_contacts import contact_channel, contact_hint
from app.utils.shema_countries import COUNTRY_CODES, is_country_code

_ROOT = Path(__file__).resolve().parents[2]

#: The one file allowed to name the network's tables. Changing this line is what a second
#: reader would cost, and that is the deliberate edit somebody has to justify.
OWNER = "_directory.py"


def _module_files() -> list[Path]:
    return sorted(
        path
        for package in ("app/services/shema", "app/api/shema")
        for path in (_ROOT / package).glob("*.py")
    )


def test_only_the_directory_owner_names_the_network_tables() -> None:
    """**The mechanism behind every consent and contact rule in this module.**

    ``ShemaIntercessor`` catches ``ShemaIntercessorConsent`` too, so one token covers the
    person, their contact, their sensitive-country flag and every consent row. A service that
    could name the table could read a contact, apply the consent gate its own way, or emit a
    person with no redaction — and the whole design rests on none of those being reachable.
    """
    offenders = [
        path.name
        for path in _module_files()
        if path.name != OWNER and "ShemaIntercessor" in path.read_text(encoding="utf-8")
    ]

    assert offenders == [], f"the network's tables are named outside {OWNER}: {offenders}"


def test_the_org_chart_never_grows_a_reference_to_the_network() -> None:
    """``docs/shema.md`` §5.7's structural rule, in the direction that is easy to add by
    accident.

    The console asserts the same separation with an import guard and says why a shape check
    would not do: *it would not survive somebody adding a* ``regionKey`` *for convenience*.
    The org chart's own tables carry no column that could point at a person in the network,
    and the file that owns the network carries nothing about a seat.
    """
    seat_columns = set(ShemaRegionTeam.__table__.columns.keys())
    assert not any("intercessor" in name for name in seat_columns)

    owner = (_ROOT / "app/services/shema" / OWNER).read_text(encoding="utf-8")
    assert "ShemaRegionTeam" not in owner
    assert "ShemaRoleChange" not in owner


def test_the_network_has_no_foreign_key_to_anything() -> None:
    """*Never joined to roles, in either direction* — read off the table, not off a docstring.

    A reference to ``users`` would be the first step of merging two models that must not
    merge, and it is also what would make *removal erases* a sweep instead of one statement.
    """
    assert ShemaIntercessor.__table__.foreign_keys == set()


def test_the_network_has_no_soft_delete_column() -> None:
    """Removal erases: no tombstone, no ``removed`` flag, no ``deleted_at``.

    Asserted as an absence because that is what the rule is. The first well-meaning follow-up
    to a deletion bug adds exactly one of these names.
    """
    columns = set(ShemaIntercessor.__table__.columns.keys())
    assert not columns & {"removed", "removed_at", "deleted_at", "is_active", "archived_at"}


def test_consent_has_no_granted_column() -> None:
    """Presence is the consent. A ``granted = false`` row would be the flag-and-retain FE-44
    §8.2 refuses by name, reached by a different route than a boolean on the person."""
    from app.db.models.shema_consent import ShemaIntercessorConsent

    columns = set(ShemaIntercessorConsent.__table__.columns.keys())
    assert not columns & {"granted", "is_granted", "withdrawn_at", "revoked_at"}
    assert tuple(column.name for column in ShemaIntercessorConsent.__table__.primary_key) == (
        "intercessor_id",
        "context",
    )


def test_the_three_consent_contexts_are_the_ladder_the_issue_describes() -> None:
    """Per context and not a single flag — and the three are the ones the issue names: being
    held and reached, being listed internally, and appearing in something shared with
    partners."""
    assert [member.value for member in ShemaConsentContext] == [
        "network",
        "directory",
        "partner-export",
    ]


def test_a_withheld_person_carries_the_marker_and_not_an_empty_string_alone() -> None:
    """FE-44 §8.1 rule 1: *return the withheld marker, not an empty string* — the redaction
    travels in the shape, so a renderer cannot leak what the payload does not hold."""
    flagged = ShemaIntercessor(name="Maria", country="EG", contact="m@e.org")
    flagged.sensitive_country = True
    plain = ShemaIntercessor(name="Ana", country="BR", contact="a@e.org")
    plain.sensitive_country = False

    assert leaving_person(flagged) == ("Maria", "", True)
    assert leaving_person(plain) == ("Ana", "BR", False)


def test_the_contact_rules_are_the_consoles_own() -> None:
    """``contactChannel`` in ``src/utils/intercessors.ts``: an e-mail, or eight digits or
    more. A server that refused what the form accepts would refuse a record for a reason
    neither side can see."""
    assert contact_channel("maria@example.org") == "email"
    assert contact_channel(" +55 11 98765-4321 ") == "phone"
    assert contact_channel("1234567") is None
    assert contact_channel("12345678") == "phone"
    assert contact_channel("ask at the church") is None


def test_a_hint_keeps_nothing_that_reaches_anybody() -> None:
    """The domain of an e-mail is often the employer, which is the identifying half."""
    assert contact_hint("maria.santos@example.org") == "m•••@•••"
    assert contact_hint("+55 11 98765-4321") == "•••21"
    assert "example.org" not in contact_hint("maria.santos@example.org")


def test_the_country_codes_are_the_list_the_console_offers() -> None:
    """Vendored rather than added as a dependency, and compared exactly as given: folding case
    here would make the two sides disagree on ``br`` in the direction nobody notices — the
    server storing what the screen would have refused."""
    assert len(COUNTRY_CODES) == 249
    assert is_country_code("BR") and is_country_code("EG") and is_country_code("TL")
    assert not is_country_code("br")
    assert not is_country_code("ZZ")
    assert not is_country_code("Brasil")
