from app.services.internalization_room.prompt_blocks import RoomFact, room_facts_block

SCENE_REHEARSALS = (
    "SCENE REHEARSALS: parts whose recorded and translated scene rehearsal has reached you: "
    "S1. Parts with none: S2."
)
EARLIER = "EARLIER PASSAGES FOR THIS TEAM: Approved: Ruth 1:1\N{EN DASH}5."
MOMENT = "MOMENT: Internalization of part 2 of 4 \N{EM DASH} the part is open."
ACCEPTED = "ACCEPTED READINGS FOR THE SCENE THIS TELLING CHECKS"


def test_two_facts_follow_in_her_order_whatever_order_they_were_handed_in() -> None:
    block = room_facts_block({RoomFact.MOMENT: MOMENT, RoomFact.SCENE_REHEARSALS: SCENE_REHEARSALS})

    assert block == f"{SCENE_REHEARSALS}\n\n{MOMENT}", (
        "o momento vinha antes dos ensaios de cena porque foi entregue primeiro"
    )


def test_a_fact_with_nothing_to_say_leaves_no_heading_behind() -> None:
    block = room_facts_block(
        {RoomFact.SCENE_REHEARSALS: "", RoomFact.EARLIER_PASSAGES: EARLIER, RoomFact.MOMENT: ""}
    )

    assert block == EARLIER, "um fato vazio deixava um cabeçalho sem nada embaixo"
    assert room_facts_block({}) == "", "sem nenhum fato o espaço depois do ledger não era vazio"


def test_the_accepted_readings_come_last_and_only_when_a_checking_turn_hands_them_in() -> None:
    ordinary = room_facts_block({RoomFact.EARLIER_PASSAGES: EARLIER, RoomFact.MOMENT: MOMENT})
    checking = room_facts_block(
        {
            RoomFact.ACCEPTED_READINGS: ACCEPTED,
            RoomFact.MOMENT: MOMENT,
            RoomFact.EARLIER_PASSAGES: EARLIER,
        }
    )

    assert ACCEPTED not in ordinary, "um turno comum levava as leituras aceitas"
    assert checking == f"{EARLIER}\n\n{MOMENT}\n\n{ACCEPTED}", (
        "as leituras aceitas não vinham por último, depois do momento"
    )
