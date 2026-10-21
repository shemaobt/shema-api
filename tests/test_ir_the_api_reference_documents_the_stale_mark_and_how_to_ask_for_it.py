import pytest

from app.main import app

THE_DOORS = [
    ("get", "/api/internalization-room/sessions/{session_id}"),
    ("post", "/api/internalization-room/sessions/{session_id}/segments/{segment_id}/divide"),
    ("post", "/api/internalization-room/sessions/{session_id}/segments/{segment_id}/replace"),
    ("post", "/api/internalization-room/sessions/{session_id}/segments/{segment_id}/sentence"),
]


def test_the_stale_mark_is_documented_as_served_only_to_a_tablet_that_asks() -> None:
    served = app.openapi()["components"]["schemas"]["SegmentView"]["properties"]["stale"]

    assert "include_stale" in served.get("description", ""), (
        "a marca regravada não dizia nas referências da API como pedi-la"
    )


@pytest.mark.parametrize(("method", "path"), THE_DOORS)
def test_every_door_that_lists_the_stretches_documents_the_query_that_asks_for_stale_ones(
    method: str, path: str
) -> None:
    parameters = app.openapi()["paths"][path][method]["parameters"]

    asking = next((one for one in parameters if one["name"] == "include_stale"), None)

    assert asking is not None, "a porta não documentava como pedir os trechos regravados"
    assert asking["schema"]["default"] is False
    assert "stale" in asking["description"]
