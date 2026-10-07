from __future__ import annotations

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]


def section(opening: str) -> str:
    start = GUIDE.index(opening)
    end = GUIDE.find("\n#", start + len(opening))
    return GUIDE[start : end if end != -1 else len(GUIDE)]


def test_one_or_two_small_details_are_offered_to_the_team_as_a_choice_never_decided_for_them() -> (
    None
):
    gap = section("### When only a detail or two is missing — offer the team the choice")

    assert "one or two small, concrete details" in gap, "the size of a gap that earns a choice"
    assert "rehearse this scene once more, or go on and fix it in the Ensaio Final" in gap, (
        "the two roads the team is offered"
    )
    assert "there you fix it together, and you check everything again with them" in gap, (
        "the reason the second road is safe"
    )
    assert "The team decides; you never decide for them" in gap
    assert (
        "An addition, a filled silence, a changed order the passage protects, a missing event "
        "or a missing scene are never carried forward"
    ) in gap, "the list of what is never offered as a choice"


def test_an_addition_is_named_without_blame_and_the_part_is_rehearsed_again_without_it() -> None:
    retelling = section("## Check every retelling — an omission must never pass")

    assert "never let it pass, however true it may sound" in retelling
    assert "isso a história não conta" in retelling, "her sentence for naming an addition"
    assert "Vamos contar de novo, só com o que a história conta?" in retelling
    assert "send them back to rehearse the part again without it" in retelling, (
        "the send-back that closes the addition"
    )


def test_the_send_off_is_the_ensaio_final_and_one_instruction_last_not_the_passage_again() -> None:
    arc = section("## How you guide the session")
    send_off = arc[arc.index("7. **The send-off — always your last word.**") :]

    assert "do NOT ask for the passage again" in arc, "the passage is not asked for a second time"
    assert "not told aloud as one piece" in arc
    assert "close the session by sending the team to the **Ensaio Final**" in send_off
    assert "then ONE instruction, last" in send_off
    assert "toquem no ponto laranja, no alto da tela, para abrir o Ensaio Final" in send_off, (
        "her instruction, word for word"
    )
    assert "never the red microphone" in send_off, "the place the Ensaio Final is not opened from"
    assert "always the last thing you say in a session" in send_off


def test_the_team_is_never_told_to_record_the_passage_again_or_to_translate_it_again() -> None:
    arc = section("## How you guide the session")
    send_off = arc[arc.index("7. **The send-off — always your last word.**") :]

    assert "Never tell them to record the passage again or to translate it again" in send_off, (
        "the two repeats her ruling of 21 September retired"
    )


def test_a_scene_told_only_orally_is_named_and_no_recording_is_claimed_the_app_did_not_report() -> (
    None
):
    arc = section("## How you guide the session")
    send_off = arc[arc.index("7. **The send-off — always your last word.**") :]

    assert "Never say they recorded a part unless the scene-rehearsal status says so" in send_off, (
        "a recording claimed without the app's status"
    )
    assert (
        "A cena 3 ainda não tem gravação: no Ensaio Final vocês gravam essa cena lá." in send_off
    ), "the way a scene told orally is named"
    assert "check it as any other telling; when it is whole, close again with the same single" in (
        send_off
    ), "a scene rehearsal that arrives after the send-off"
    assert "that joined recording is the team's first oral draft" in arc, (
        "what the scene recordings joined in the Ensaio Final are"
    )


def test_the_session_opens_with_the_familiarization_its_numbered_scenes_and_its_closing() -> None:
    moments = section("## The three moments — Familiarization, Internalization, Articulation")

    assert "Vamos começar pela Familiarização. Primeiro eu conto a passagem inteira." in moments, (
        "the first words of the session"
    )
    assert "Essa passagem tem quatro cenas." in moments
    assert "Cena 1:" in moments, "the scenes are named by their number"
    assert (
        "O que chamou a atenção de vocês nessa passagem? Conversem entre vocês. Se tiver alguma "
        "dúvida, me perguntem. Quando estiverem prontos, me digam e a gente vai pra "
        "Internalização da primeira cena."
    ) in moments, "the last words of the Familiarization, said whole"
    assert (
        'end that turn with the last two sentences of that closing: *"Se tiver alguma dúvida, '
        "me perguntem. Quando estiverem prontos, me digam e a gente vai pra Internalização da "
        'primeira cena."'
    ) in moments, "a comment before the team's word is answered and ends with the last two"


def test_the_first_scene_opens_on_the_teams_word_with_no_question_left_open() -> None:
    moments = section("## The three moments — Familiarization, Internalization, Articulation")

    assert (
        "The first part is opened only when the team tells you it is ready, with no question "
        "left open — never in the reply to their comment or question about the whole"
    ) in moments
    assert "Vamos pra Internalização da cena 2." in moments, "every scene opening begins with it"
    assert "Vamos pra Articulação da cena 2." in moments, "the first fence follows it"


def test_where_the_team_is_is_said_and_the_next_scene_waits_but_never_after_the_send_off() -> None:
    moments = section("## The three moments — Familiarization, Internalization, Articulation")

    assert (
        "Estamos na Articulação da cena 2. Primeiro a gente termina essa cena; depois vem a cena 3."
    ) in moments, "the answer to a next scene asked for before this one came back whole"
    assert "you never say the where-we-are sentence" in moments, "after the send-off"


def test_a_scene_told_ahead_is_kept_and_a_later_scene_asked_first_is_not_opened_out_of_order() -> (
    None
):
    moments = section("## The three moments — Familiarization, Internalization, Articulation")

    assert "the scenes always open in order, the first scene first, on the team's word" in moments
    assert "vocês já contaram parte disso" in moments, "what the voice says when that part comes"
    assert "Never correct the team's word: do what they mean." in moments, (
        "the team's own word for a moment"
    )


def test_a_part_opening_always_ends_with_the_fixed_closing_and_nothing_after_it() -> None:
    opening = section("## Opening a part — close it with these words")

    assert ("your last words are always these, and nothing comes after them") in opening
    assert (
        "O que chamou a atenção de vocês nessa cena? Conversem entre vocês. Essa cena ficou "
        "clara? Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai "
        "pro ensaio."
    ) in opening, "her closing, word for word"


def test_the_fence_waits_for_the_teams_word_and_an_entendi_with_a_question_is_not_that_word() -> (
    None
):
    opening = section("## Opening a part — close it with these words")
    fence = section("## The rehearsal block — fence what goes into the rehearsal")

    assert "Never open a part and give the fenced block in the same turn." in opening
    assert "Entendi. E …?" in opening, "an understanding that comes with a question"
    assert "is not the team's word to rehearse" in opening
    assert "answer the question from the map, end with the closing's last two sentences" in opening
    assert "o passo a passo" in opening, "a request to hear only the story"
    assert "with no number or label on any step" in opening
    assert "Agora vou dizer tudo o que deve entrar no ensaio de vocês." in fence
    assert "Agora podem ensaiar." in fence


def test_a_part_not_yet_opened_is_opened_first_even_when_it_was_heard_inside_the_whole() -> None:
    opening = section("## Opening a part — close it with these words")

    assert "Hearing a part inside the whole passage is not its opening" in opening
    assert (
        "open it first, ending with the closing, and give the fenced block only after they come "
        "back to you"
    ) in opening
    assert (
        "unless it comes with a question about the story or they say they have not understood it"
    ) in opening, "a request that comes with a question is answered first"


def test_the_send_back_after_a_checked_telling_gives_the_fenced_block_again() -> None:
    fence = section("## The rehearsal block — fence what goes into the rehearsal")

    assert (
        "when you send them back to rehearse after checking a telling, first name what was "
        "missing or added (outside the fence), then give the fenced block again"
    ) in fence


def test_a_part_told_ahead_still_passes_both_moments_and_a_comment_ends_as_the_opening_does() -> (
    None
):
    moments = section("## The three moments — Familiarization, Internalization, Articulation")
    opening = section("## Opening a part — close it with these words")

    assert (
        "Every part still goes through its Internalization — its Internalization line, its "
        "opening, the fixed closing and the team's word — and its Articulation"
    ) in moments
    assert "end that turn with the last two sentences of the closing" in opening, (
        "a comment between the opening and the fenced block"
    )
    assert (
        "The opening of the whole passage when the session opens is the Familiarization, not "
        "the opening of a part: it ends with its own closing"
    ) in opening
    assert "the send-off (its one instruction, the orange dot, stays your last word)" in opening


def test_an_omission_in_a_retelling_never_passes_silently_the_guide_names_it_aloud() -> None:
    retelling = section("## Check every retelling — an omission must never pass")

    assert "**If even one thing is missing, you must say so**" in retelling, (
        "the omission is named, warmly, every time"
    )
    assert "there's someone in this part you haven't mentioned yet" in retelling, (
        "her sentence for naming it"
    )
    assert (
        "Never praise a retelling as complete, and never move on from it, while anything the "
        "map gives for that part is missing from it"
    ) in retelling, "no praise and no moving on over a gap"
