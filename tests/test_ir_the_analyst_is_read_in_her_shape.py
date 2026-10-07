import json

from app.services.internalization_room.back_translation import FindingKind, _parse_analysis
from tests.turn_harness import told_stretches


def _read(*findings: dict[str, object]):
    return _parse_analysis(json.dumps({"findings": list(findings)}), told_stretches())


def test_a_finding_naming_her_frase_lands_on_that_stretch() -> None:
    read = _read({"kind": "addition", "note": "as noras pediram", "frase": 2})

    assert read is not None, "a resposta no formato dela era recusada inteira"
    (finding,) = read.findings
    assert (finding.kind, finding.chunk, finding.segment_id) == (
        FindingKind.ADDITION,
        2,
        "segmento-2",
    )


def test_a_missing_element_sits_after_the_frase_she_names() -> None:
    read = _read({"kind": "missing", "note": "a fome", "frase": 1})

    assert read is not None
    (finding,) = read.findings
    assert finding.segment_id == "segmento-2", "o que falta depois da frase 1 começa na frase 2"


def test_a_nuance_is_read_never_voiced_and_never_refuses_the_reply() -> None:
    read = _read(
        {
            "kind": "nuance",
            "note": "a espera",
            "frase": 1,
            "quote": "ela mandou",
            "story": "ela insistiu",
        }
    )

    assert read is not None, "um tipo que o parser não conhecia recusava a leitura inteira"
    assert read.findings == []
