from __future__ import annotations

import re

from app.services.internalization_room.languages import FLOOR

#: What an app-owned block says when the turn has none. The Validator is shared with every
#: conversation turn, where there is no finding, no ordered closing and no telling-back, and
#: an empty heading there reads as evidence withheld rather than as a block that does not
#: apply. The prompt says so in words; this is the same sentence in the slot itself.
NOT_THIS_TURN = "(não se aplica a este turno)"

#: What the Validator is told when nobody spoke this turn, in the session's own language.
#: Keyed by language code, in the shape the other per-language tables use — an unclaimed
#: language falls back to the authored English line. Two cases per language: the opening
#: turn, where nobody has spoken yet, and the verdict path, where the team has spoken —
#: outside the conversation, into the telling-back — and the opening line would say the
#: opposite, which is the sentence the Validator quoted back when it refused the verdict.
_NO_TEAM_UTTERANCE: dict[str, dict[str, str]] = {
    "pt": {
        "opening": "(a equipe ainda não falou — abertura da sessão)",
        "told_back": (
            "(a equipe não falou nesta conversa; o que ela traduziu está no bloco abaixo)"
        ),
    },
    "en": {
        "opening": "(the team has not spoken yet — session opening)",
        "told_back": (
            "(the team has not spoken in this conversation; what they translated is in the "
            "block below)"
        ),
    },
    "es": {
        "opening": "(el equipo aún no ha hablado — apertura de la sesión)",
        "told_back": (
            "(el equipo no ha hablado en esta conversación; lo que tradujeron está "
            "en el bloque de abajo)"
        ),
    },
}


def _nobody_spoke_this_turn(telling_back: str, language_code: str) -> str:
    """What stands where the team's utterance would, on a turn that had none."""
    messages = _NO_TEAM_UTTERANCE.get(language_code, _NO_TEAM_UTTERANCE[FLOOR])
    return messages["told_back"] if telling_back else messages["opening"]


OPENING_MOVEMENT_MARK = "[[CENA]]"
_MOVEMENT_MARK = re.compile(r"^[ \t]*\[\[CENA\]\][ \t]*$", re.M)


def split_opening_movements(draft: str) -> tuple[str, list[str]]:
    """The draft with the mark taken out, and its two movements when the mark is exact.

    The text comes back mark-free whatever happens: a marker read aloud by the synthesiser
    is the one outcome nothing downstream recovers from. The movements come back empty
    unless the mark stands exactly once, alone on its own line, with speech on both sides —
    a half-offered structure has to be indistinguishable from no structure at all, because
    an opening told in one breath is what the room already does well.
    """
    parts = _MOVEMENT_MARK.split(draft)
    clean = _MOVEMENT_MARK.sub("", draft).replace(OPENING_MOVEMENT_MARK, " ")
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    if len(parts) != 2:
        return clean, []
    whole, scene = (part.strip() for part in parts)
    if not whole or not scene:
        return clean, []
    return clean, [whole, scene]


OPENING_INSTRUCTION = (
    "A sessão está começando agora e a equipe ainda não falou. Abra a sessão: "
    "apresente-se brevemente, dê à equipe o todo antes das partes, e fique com a "
    "equipe na compreensão: o convite ao ensaio espera até ela mostrar que tem a parte."
)

ALREADY_MET_INSTRUCTION = (
    "A sessão desta passagem está começando agora e a equipe ainda não falou. "
    "Vocês acabaram de percorrer juntos o panorama do livro, então a equipe já "
    "conhece você: NÃO se apresente de novo nem diga seu nome. Entre direto na "
    "passagem: dê à equipe o todo antes das partes, e fique com a equipe na "
    "compreensão: o convite ao ensaio espera até ela mostrar que tem a parte."
)

OPENING_MOVEMENT_INSTRUCTION = (
    "Escreva esta abertura em dois movimentos, separados por uma linha contendo "
    f"apenas {OPENING_MOVEMENT_MARK} e nada mais. Antes da linha: o todo da "
    "passagem, o arco e o tom. Depois da linha: abra a primeira cena e fique nela "
    "com a equipe; o convite ao ensaio não fecha a abertura. "
    "Não escreva a marca em nenhum outro lugar e não a comente."
)


VALIDATOR_USER_MESSAGE = "Julgue a resposta rascunhada."
