"""The decision→column mapping, as an execution path rather than a correspondence table.

The four Parte C decision strings and the six board columns are different key spaces, and
the correspondence is a mapping and not an identity — note ``declined`` ↔ ``recusado``
(contract §6.5). GATE-02 D6 turned the table into behaviour: recording a decision moves
the card, so ``save_evaluation`` reads this map inside the same transaction that writes
the decision, and BE-08 (OBT-457) reads the same map when a hand moves a card that a
decision also implies.

The implication runs one way only. A decision implies a column; a column never implies a
decision — the mesa may still drag a card it never evaluated, and nothing here or in
BE-08 writes a decision from a stage. ``triagem`` and ``analise`` are absent because they
precede any decision, which is why this is a map over ``RRDecision`` and not over
``RRStage``: totality in the direction that executes, and no entry to invent in the
direction that must not.
"""

from app.db.models.resource_request import RRDecision, RRStage

DECISION_STAGE: dict[RRDecision, RRStage] = {
    RRDecision.APPROVED: RRStage.APROVADO,
    RRDecision.CONDITIONAL: RRStage.CONDICIONAL,
    RRDecision.REVISE: RRStage.REVISAR,
    RRDecision.DECLINED: RRStage.RECUSADO,
}
