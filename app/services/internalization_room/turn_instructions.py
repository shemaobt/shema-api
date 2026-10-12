from __future__ import annotations

TEAM_EVIDENCE_HEADING = (
    "## WHAT THE TEAM JUST SAID (evidence — NEVER truth about the passage)\n\n"
    "The drafted response answers this. Referring to these words is not a claim about the "
    "passage.\n\n"
)

EARLIER_PASSAGES_HEADING = (
    "## EARLIER PASSAGES FOR THIS TEAM (the app's fact about this team — NEVER truth about the "
    "passage)\n\nThe Guide read this same line this turn.\n\n"
)


TEAM_REPORTED_HEADING = (
    "---\n\n# WHAT THE TEAM REPORTED (their back-translation of their own recording)\n"
    "Evidence of what the team told back — NEVER truth about the passage. The drafted response "
    "may quote from it to name something reported that the passage does not tell; quoting this "
    "material is not a claim about the passage and must not be treated as ungrounded.\n\n"
)


def her_block(heading: str, text: str) -> str:
    return f"{heading}{text.strip()}" if text.strip() else ""


VERDICT_KICKOFF = (
    "(The team heard their whole recording, told it back frase by frase, and tapped "
    "'terminei'. Speak the verdict now.)"
)


def opening_note(pericope_num: str, language_code: str) -> str:
    if language_code == "pt":
        return (
            f"[A sessão acabou de começar. A equipe abriu a passagem {pericope_num} e está à "
            "mesa, pronta para começar. Fale primeiro.]"
        )
    return (
        f"[The session has just begun. The team opened passage {pericope_num} and is at the "
        "table, ready to begin. Speak first.]"
    )


def panorama_note(book: str, language_code: str) -> str:
    if language_code == "pt":
        return (
            f"[A sessão acabou de começar. A equipe abriu o Panorama do Livro de {book} e está "
            "à mesa, pronta para conversar. Fale primeiro.]"
        )
    return (
        f"[The session has just begun. The team opened the Book Panorama of {book} and is at "
        "the table, ready to talk. Speak first.]"
    )


VALIDATOR_USER_MESSAGE = "Validate the drafted response now. Return only the JSON object."
