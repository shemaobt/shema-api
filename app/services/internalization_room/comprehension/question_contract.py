"""Spoken question-shape rules for app-owned comprehension probes.

The application chooses the evidence method. The Guide only turns that method into a
short, grounded oral question. Keeping these rules deterministic prevents a nominally
"independent" second check from becoming the same leading question in different words.
"""

from __future__ import annotations

from app.services.internalization_room.comprehension.evidence import EvidenceMethod

_CONTRACTS: dict[EvidenceMethod, str] = {
    EvidenceMethod.FREE_BRIDGE_RETELL: (
        "QUESTION SHAPE: Invite one natural telling of the authorized comfortable scope. "
        "Do not list its details, supply its events, interrupt it with checks, or turn it "
        "into a checklist."
    ),
    EvidenceMethod.MICRO_TELLBACK: (
        "QUESTION SHAPE — micro_tellback: Ask one open who/what/where/how-many question "
        "whose answer is one short meaning fragment. Do not state, quote, paraphrase, or "
        "offer the expected answer; do not append a yes/no confirmation."
    ),
    EvidenceMethod.TRUE_EVENT_SEQUENCE: (
        "QUESTION SHAPE — true_event_sequence: Give exactly two short events that both "
        "occur in the authorized canonical material, then ask which happened first. Do not "
        "state the correct order, add a third event, or invent a false distractor. This is "
        "prompted recognition, so it must test sequence rather than repeat the previous "
        "wording."
    ),
    EvidenceMethod.ROLE_OR_PLACE_CHOICE: (
        "QUESTION SHAPE — role_or_place_choice: Ask which of exactly two map-grounded "
        "people or places fills the one authorized role or location. Both options must "
        "occur in the authorized canonical material; never invent a distractor. If two "
        "safe candidates are not present there, use one open who/where fragment question "
        "instead. Do not reveal which option is correct."
    ),
    EvidenceMethod.SIGNIFICANT_ABSENCE_CHECK: (
        "QUESTION SHAPE — significant_absence_check: Ask one open question about what the "
        "passage says or leaves unsaid in the authorized domain. You may name the domain, "
        "but do not state the missing claim, suggest the expected silence, or ask 'it does "
        "not say X, right?'."
    ),
    EvidenceMethod.PEER_CONFIRMATION: (
        "QUESTION SHAPE — peer_confirmation: Invite a different team member to "
        "independently state this one meaning in their own words. Do not quote the first "
        "answer, ask whether they agree, request a bare yes/no, or tell them what the "
        "answer should contain."
    ),
}


def question_contract(method: EvidenceMethod) -> str:
    return _CONTRACTS[method]
