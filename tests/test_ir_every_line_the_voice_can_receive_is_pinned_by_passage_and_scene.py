from __future__ import annotations

import pytest

from app.services.internalization_room.canon.accepted_readings import (
    accepted_lines,
    accepted_readings_of,
)
from app.services.internalization_room.canon.scene_ids import scene_ids_for

PINNED: dict[str, dict[str, list[str]]] = {
    "P08": {
        "S1": [
            "- R1: The question of 3:1 means that Naomi will seek the resting place: a telling that says it as a statement ('I will seek', 'I must seek a resting place for you') keeps the meaning and is accepted without comment; a telling that has Naomi say she will not seek it (the question lost, so it reads as a refusal) is offered back gently with the text's words. 'Is not Boaz our kinsman?' told as 'Boaz is our kinsman' is accepted without comment.",
            '- R2: A team telling that keeps "a resting place" and adds marriage or a husband, as 1:9 said, is accepted without comment; one that puts marriage in place of "a resting place" is offered back gently.',
            "- R4: A team rendering that keeps the idea of rest ('lugar de descanso') is correct without comment.",
            "- R9: A telling that names Ruth or Boaz keeps the meaning and is accepted without comment.",
            "- R10: In a team telling, 'parente', 'relative', 'kinsman' or 'da nossa família' are correct here; accept them without comment.",
            "- R11: 3:3: one garment or several are both correct. 3:3: 'do not be known to the man' and 'do not let the man know you are there' are both correct. 3:4: 'know the place where he lies' means notice it or mark it; both are correct. All of these are accepted without comment.",
        ],
        "S2": [
            "- R3: 'Ruth said she would do everything', 'Ruth said yes to all of it' keep the meaning; accept without comment.",
            "- R8: With or without 'to me' is correct, accepted without comment.",
            "- R9: A telling that names Ruth or Boaz keeps the meaning and is accepted without comment.",
        ],
    },
    "P09": {
        "S2": [
            "- R1: A team telling 'she asked him to marry her' is not an addition, but the wing is missing: offer it back as a missing detail.",
        ],
    },
    "P10": {
        "S1": [
            "- R1: 'Six measures of barley' ('seis medidas de cevada') is accepted without comment.",
            "- R2: A telling in which he says it to Ruth, or says 'no one must know', keeps the meaning; accept it without comment. 'The woman' or 'a woman' ('a mulher' / 'uma mulher') are both correct.",
            "- R3: A telling that uses the names Boaz, Ruth or Naomi keeps the meaning and is accepted without comment.",
            "- R8: 'cloak', 'shawl', 'manto', 'capa' are all correct.",
            "- R11: 3:15: Boaz says 'give / bring the cloak that is on you, and hold it'; 'hold out the cloak', 'bring the cloak', 'give me the cloak' and 'hold it' ('segure a capa') are all correct; 'he laid it on her' and 'on her back' ('lhe pôs às costas') are both correct. All of these are accepted without comment.",
        ],
        "S2": [
            "- R3: A telling that uses the names Boaz, Ruth or Naomi keeps the meaning and is accepted without comment.",
            "- R4: A telling that says the barley was for her mother-in-law keeps the meaning. So does a telling that adds 'home' ('do not go home empty') while keeping 'your mother-in-law'. Accept both without comment.",
            "- R5: A telling 'how did it go, my daughter?' ('como foi, minha filha?') keeps the meaning but not the same words as 3:9: a nuance, named once, not sent back.",
            "- R6: 'Sit still', 'wait' and 'stay here' ('fique quieta', 'espere', 'fique aqui') are correct; accept them without comment. A telling that ties 'today' to something else (for example 'the matter of today') keeps most of the meaning; it is a nuance, named once and not sent back.",
            "- R9: A telling that names some of what he did at night, in the text's words (he asked who she was; he said: if the nearer redeemer will redeem you, good; if he does not want to redeem you, I will redeem you; he gave her the barley), keeps the meaning; accept it without comment.",
            "- R11: 3:18: 'how the matter falls' — 'how it turns out', 'how the matter ends', 'como esse assunto vai terminar' and the word-for-word 'como vai cair' are all correct. 3:16: 'all that the man did for her' — 'all that happened', 'everything he did' are correct. All of these are accepted without comment.",
        ],
    },
    "P11": {
        "S1": [
            "- R2: A team rendering with any non-name ('amigo', 'você aí', or the like) is correct. The voice accepts such a rendering and does not correct or remark on it.",
        ],
        "S2": [
            "- R11: 'I will uncover your ear' means 'I resolved to tell you'; the plain form is correct.",
            "- R13: 4:3: the voice says Naomi 'is selling' the field; a team telling 'sold' is correct. 'Our brother Elimelech' means a kinsman: 'our brother' and 'our kinsman' are both correct. 4:4: 'before those seated' and 'before the inhabitants' are both correct.",
        ],
        "S4": [
            "- R5: A team telling 'and gave it to Boaz' is correct, not an addition. The voice accepts it and does not correct or remark on it.",
        ],
    },
    "P12": {
        "S1": [
            "- R1: The three names are a list, not an order of events: a telling that names the sons in another order is accepted without comment.",
            "- R2: 'Bought' told as 'redeemed' or 'acquired' is accepted without comment.",
            "- R6: A telling that Boaz married Ruth, or is marrying her, keeps the meaning of his declaration; accept it without comment.",
            "- R11: 4:10: 'from his kindred'; 'his kindred', 'his brothers', 'his family' are all correct. 4:10: Boaz says he has bought Ruth 'for myself, to be my wife'; 'bought' and 'acquired' are both correct. All of these are accepted without comment.",
        ],
        "S2": [
            "- R6: A telling that Boaz married Ruth, or is marrying her, keeps the meaning of his declaration; accept it without comment.",
            "- R8: 'We are witnesses' is the same answer and is accepted without comment.",
            "- R13: In a team telling, worth, standing, strength, prosperity or means are correct; accept them without comment.",
        ],
    },
    "P13": {
        "S1": [
            "- R1: A team telling such as 'God gave them a son' keeps the meaning; accept it without comment.",
            "- R9: A telling that recalls Boaz's words at the gate — he bought Ruth to raise up the name of the dead — is correct; accept it without comment.",
        ],
        "S2": [
            "- R2: The women bless YHWH and speak to Naomi; a telling that has the women bless Naomi herself is a nuance: name it once.",
            "- R3: A telling in which the child is the redeemer keeps the meaning; accept it without comment.",
            "- R4: A telling that says 'Ruth' keeps the meaning; accept it without comment.",
            "- R9: A telling that recalls Boaz's words at the gate — he bought Ruth to raise up the name of the dead — is correct; accept it without comment.",
        ],
        "S3": [
            "- R5: A telling 'she took care of him' or 'she raised him' keeps the meaning; accept it without comment.",
            "- R8: A team telling 'King David' ('o rei Davi') is a nuance: the voice names it once — 'a história dá só o nome dele, Davi' ('the story gives only his name, David') — without a send-back, and moves on.",
            "- R9: A telling that recalls Boaz's words at the gate — he bought Ruth to raise up the name of the dead — is correct; accept it without comment.",
        ],
    },
    "P14": {
        "S1": [
            "- R1: Other words for 'fathered' ('begot', 'was the father of', 'had a son') keep the meaning; accept them without comment.",
            "- R2: A team telling that recalls Perez as the son Tamar bore to Judah (4:12), or Obed as the son Ruth bore (4:13), is correct; accept it without comment.",
            "- R3: A team telling that recalls what the book told at 4:13 — YHWH gave her conception, and she bore a son — is correct; accept it without comment.",
            "- R4: A team telling 'King David' ('o rei Davi') is a nuance: the voice names it once — 'a história dá só o nome dele, Davi' ('the story gives only his name, David') — without a send-back, and moves on.",
            "- R9: 4:18 'these are the generations of Perez': 'the descendants of Perez', 'the family line of Perez' and similar wordings are correct. 'Fathered': 'fathered', 'begot', 'was the father of' and 'had a son' are all correct. Names as the team's own Bible spells them (e.g. 'Rão', 'Naassom', 'Salmom') are correct. Accept these forms without comment.",
        ],
    },
}

RUTH = [f"P{n:02d}" for n in range(1, 15)]
LINES = [
    pytest.param(pericope, scene, line, id=f"{pericope} {scene} {line.split(':', 1)[0][2:]}")
    for pericope, scenes in PINNED.items()
    for scene, lines in scenes.items()
    for line in lines
]


@pytest.mark.parametrize(("pericope", "scene", "line"), LINES)
def test_every_line_the_voice_can_receive_is_her_line_character_for_character(
    pericope: str, scene: str, line: str
) -> None:
    lines = accepted_lines(accepted_readings_of(pericope).items, scene)

    assert line in lines, f"a linha de {pericope} {scene} mudou e chegaria à voz sem ser vista"


def test_her_table_is_46_lines_in_14_blocks_and_no_other_scene_of_ruth_has_one() -> None:
    blocks = {
        (pericope, scene): lines
        for pericope in RUTH
        for scene in scene_ids_for(pericope)
        if (lines := accepted_lines(accepted_readings_of(pericope).items, scene))
    }

    assert sum(len(lines) for lines in blocks.values()) == 46
    assert len(blocks) == 14
    assert blocks == {
        (pericope, scene): lines
        for pericope, scenes in PINNED.items()
        for scene, lines in scenes.items()
    }, "uma cena ganhou ou perdeu uma linha, ou as linhas mudaram de ordem"
