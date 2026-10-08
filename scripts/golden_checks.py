"""Marcia's `mechanicalChecks`, ported whole as a pure function over one played turn.

Read from `src/golden/run.ts` in `shemaobt/Tripod-Internalization` at `533b6e3`, the commit
`docs/doctrine/DOCTRINE_PIN` names, where the function holds seven checks. Her runner at the
freeze (`docs/doctrine/FREEZE_PIN`, 18fa7c4) holds many more and takes the earlier replies as a
third argument; this port is the seven and does not follow it. The rules are hers and so are
the messages, in her English, because a report of ours is read beside one of hers and a rule
renamed on our side is a rule the two stacks no longer share. No check is added, none is
dropped, none is loosened. These are "the cheap, unambiguous ones" the runner makes without a
judge; the rest of her `expect` keys — `opens_more`, `names_gap`, `no_spoiler` — are the
judge's to score.

Her regexes run without the `u` flag, so her `\\b` is ASCII-only where Python's is
Unicode-aware; `scripts/bt_golden_checks.py` measures the difference. Nothing a Guide turn
says separates the two here: the words on either side of every `\\b` below are unaccented.
"""

from __future__ import annotations

import unicodedata
from typing import Any

import regex


def _her(pattern: str, flags: int = regex.IGNORECASE) -> regex.Pattern[str]:
    ascii_like_javascript = (
        pattern.replace(r"\b", r"(?a:\b)").replace(r"\w", r"(?a:\w)").replace(r"\d", "[0-9]")
    )
    return regex.compile(ascii_like_javascript, flags)


def _fold(text: str) -> str:
    return regex.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


_HANDS_THE_WORD_BACK = (
    "Se já entenderam, me digam e a gente vai pro ensaio.",
    "If you have understood it, tell me and we will go to the rehearsal.",
)


def _rehearsal_invited(text: str) -> bool:
    folded = _fold(text)
    for sentence in _HANDS_THE_WORD_BACK:
        folded = folded.replace(sentence, " ")
    return _REHEARSAL.search(folded) is not None


_REHEARSAL = _her(r"\bensai(em|ar|o)\b|rehears")
_THE_PAIRING_DENIED = _her(
    r"n[ãa]o (diz|fala|conta|sabemos)[^.]{0,60}(quem|qual|se)\b|quem casou com quem"
    r"|qual casou com qual|sem dizer (quem|qual)"
)
_SENTENCE_END = _her(r"(?<=[.!?…])\s+")
_BOTH_SONS = _her(r"(Malom|Mahlon) (e|and) (Quiliom|Chilion)")
_BOTH_WOMEN = _her(
    r"(Orfa|Orpah) (e|and) (a outra |the other )?(Rute|Ruth)"
    r"|(Rute|Ruth) (e|and) (a outra |the other )?(Orfa|Orpah)"
)
_A_WOMAN_AND_HER_SON = _her(
    r"(Rute|Ruth)[^.]{0,40}\b(Malom|Mahlon)\b|(Malom|Mahlon)[^.]{0,40}\b(Rute|Ruth)\b"
    r"|(Orfa|Orpah)[^.]{0,40}\b(Quiliom|Chilion)\b|(Quiliom|Chilion)[^.]{0,40}\b(Orfa|Orpah)\b"
)
_MARRIED = _her(r"casou|casaram|esposa|mulher de|married|wife|pegou|pegaram")
_A_DENIAL = _her(
    r"n[ãa]o (diz|fala|conta|sabemos|sei)|sem dizer|not (say|tell)|does not|doesn't|never says"
)


def _pairing_voiced(text: str) -> bool:
    if _THE_PAIRING_DENIED.search(text):
        return False
    for sentence in _SENTENCE_END.split(text):
        if _BOTH_SONS.search(sentence) and _BOTH_WOMEN.search(sentence):
            continue
        if (
            _A_WOMAN_AND_HER_SON.search(sentence)
            and _MARRIED.search(sentence)
            and not _A_DENIAL.search(sentence)
        ):
            return True
    return False


_RECORD = _her(r"grav")
_NAMES_THE_RECORDING = _her(r"grava")
_A_CHOICE_ASKED = (
    _her(r"\b(querem|preferem|quer|prefere|podem|pode|escolh\w*)\b[^.!?]{0,160}\bou\b"),
    _her(r"\b(ou|Ou)\b[^.!?]{0,60}\b(podem|preferem|querem|seguir)\b[^.!?]{0,80}grava"),
    _her(r"duas escolhas|dois caminhos|qual caminho|dois jeitos|duas op[cç][õo]es"),
)
_THE_RECORDING_AS_A_ROAD = _her(r"\bou\b[^.?!]{0,80}grava|grava[^.?!]{0,80}\bou\b")
_THE_ENSAIO_FINAL = _her(r"ensaio final|final rehearsal")
_A_CHOICE_IN_ONE_SENTENCE = (
    _her(r"\b(querem|preferem|quer|prefere|podem|pode|escolh\w*)\b[^.!?]{0,160}\bou\b"),
    _her(r"\bou\b[^.!?]{0,60}\b(podem|preferem|querem|segu\w*|acert\w*|continu\w*)\b"),
    _her(
        r"\b(do you want|would you (like|rather|prefer)|you can|you may|you could|choose)\b"
        r"[^.!?]{0,160}\bor\b"
    ),
    _her(r"\bor\b[^.!?]{0,60}\b(you can|would you rather|do you prefer|go on)\b"),
)
_TWO_ROADS_ANNOUNCED = _her(
    r"duas escolhas|dois caminhos|qual caminho|dois jeitos|duas op[cç][õo]es"
    r"|two (choices|paths|ways|options)|which (path|way|road)"
)


def _offers_choice(text: str) -> bool:
    return _NAMES_THE_RECORDING.search(text) is not None and any(
        asked.search(text) for asked in _A_CHOICE_ASKED
    )


def _offers_choice_final(text: str) -> bool:
    sentences = _SENTENCE_END.split(text)
    for at, sentence in enumerate(sentences):
        in_one = any(asked.search(sentence) for asked in _A_CHOICE_IN_ONE_SENTENCE)
        if in_one and _THE_ENSAIO_FINAL.search(sentence):
            return True
        spelled_out = " ".join(sentences[at : at + 4])
        if _TWO_ROADS_ANNOUNCED.search(sentence) and _THE_ENSAIO_FINAL.search(spelled_out):
            return True
    return False


_SCENE_BY_SCENE = _her(r"cena por cena|por cena|parte por parte")
_SENT_BACK = _her(
    r"(?<!\b(não|sem|nenhum|nem)\b[^.?!:;,]{0,30})acréscimo"
    r"|(?<!\b(não|nem) )(vamos|podem|querem|precisam|têm que|tem que) (contar|ensaiar)"
    r"[^.?!]{0,40}de novo"
    r"|cont(em|ar|a) de novo,? (só )?(sem|com|até)"
    r"|ensai(em|ar) (essa|esta|a) parte de novo"
    r"|isso (a história|a passagem) não conta(?![^.?!]*(vocês|guard|respeit|proteg|silêncio))"
)
_THE_NOUN_DEMANDED = _her(
    r"(?<!\b(não|nem) )(precisa|precisam|falta|faltou|tentem|coloquem|usem|ponham|botem"
    r"|tem que|têm que|onde (está|fica)|cadê)[^.?!]{0,40}(?<!\p{L})"
    r'(a palavra|o substantivo|o termo|["“]?bondade fiel)'
    r"|(?<!\p{L})(a palavra|o termo|bondade fiel)[^.?!]{0,30}(?<!\b(não|nem) )"
    r"(falt|precisa|tem que|têm que|ficou de fora|ficou faltando)"
    r"|(?<!\p{L})(a palavra|o termo) (certa|certo|exata|exato) (é|seria|era)"
    r"|não é (a palavra|o termo) (certa|certo|exata|exato)"
    r"|(?<!\b(não|nem) )falt(a|ou)[^.?!]{0,40}bondade"
)
_FENCE_OPENS = _her(
    r"vou dizer tudo o que deve entrar no ensaio de vocês"
    r"|everything that should go into your rehearsal"
)
_FENCE_CLOSES = _her(r"agora podem ensaiar|now you can rehearse")
_COMMENTARY_IN_THE_FENCE = _her(
    r"\brepar(em|a)\b|\blembr(em|a)\b|a história não (conta|diz|fala)|não (fala|diz) o nome"
    r"|de propósito|é só isso|usem as mãos|com as mãos|encen(em|ar)"
    r"|\b(três|duas|quatro) (coisas|pedaços|partes)\b"
)
_COMMENTARY_AFTER_THE_FENCE = _her(
    r"\brepar(em|a)\b|\blembr(em|a)\b|a história não (conta|diz|fala)"
)
_THE_TAIL_AFTER_THE_FENCE = _her(
    r"se tiver alguma dúvida, me perguntem|se já entenderam, me digam"
    r"|if you have any questions, ask me|if you have understood it, tell me"
)
_ORDINAL = (
    r"primeir[oa]|segund[oa]|terceir[oa]|quart[oa]|quint[oa]|sext[oa]|s[ée]tim[oa]|oitav[oa]"
    r"|non[oa]|d[ée]cim[oa]|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth"
)
_NUMBER_WORD = (
    r"\d{1,2}|um|dois|tr[êe]s|quatro|cinco|seis|sete|oito|nove|dez"
    r"|one|two|three|four|five|six|seven|eight|nine|ten"
)
_SENTENCE_START = r"(?:^|[.!?…]\s+|\n\s*)"
_LABEL_MARK = r"(?:\s*[,:;—\u2013]|\s+-)"
_STEP_LABELS = (
    _her(rf"(?<!\p{{L}})(passo|step)\s+({_NUMBER_WORD})(?!\p{{L}})"),
    _her(rf"(?<!\p{{L}})({_NUMBER_WORD})\s+(passos|steps)(?!\p{{L}})"),
    _her(rf"{_SENTENCE_START}(\d{{1,2}}[.)º°])\s", 0),
    _her(
        rf"{_SENTENCE_START}((?:{_ORDINAL})(?:\s+(?:passo|coisa|parte|ponto|step|thing|part))?"
        rf"{_LABEL_MARK})"
    ),
)
_ORDINAL_OPENING_A_SENTENCE = _her(rf"{_SENTENCE_START}({_ORDINAL})(?![\p{{L}}-])")
_ACCORDING_TO = _her(r"^\s+(?:o|a|os|as|ele|ela|eles|elas)(?!\p{L})")


def _step_label_in_fence(inside: str) -> str | None:
    text = unicodedata.normalize("NFC", inside)
    for label in _STEP_LABELS:
        hit = label.search(text)
        if hit:
            return regex.sub(r"^[.!?…\s]+", "", hit[0]).strip()
    starts = [
        opening[1].lower()
        for opening in _ORDINAL_OPENING_A_SENTENCE.finditer(text)
        if not (
            opening[1].lower().startswith("segund") and _ACCORDING_TO.match(text[opening.end() :])
        )
    ]
    return " … ".join(starts) if len(set(starts)) >= 2 else None


def _fence_faults(guide: str) -> list[str]:
    opens = _FENCE_OPENS.search(guide)
    closes = _FENCE_CLOSES.search(guide)
    if not opens or not closes or closes.start() < opens.start():
        return [
            "the invitation to rehearse has no fenced block (opening line … 'Agora podem ensaiar.')"
        ]
    faults = []
    inside = guide[opens.start() : closes.start()]
    commentary = _COMMENTARY_IN_THE_FENCE.search(inside)
    said = commentary[0] if commentary else _step_label_in_fence(inside)
    if said:
        faults.append(f'commentary inside the fenced rehearsal block: "{said}"')
    after = guide[closes.end() :]
    if _COMMENTARY_AFTER_THE_FENCE.search(after) or _THE_TAIL_AFTER_THE_FENCE.search(after):
        faults.append("commentary after the fence's closing line")
    return faults


_PART_CLOSING = (
    "O que chamou a atenção de vocês nessa cena? Conversem entre vocês. Essa cena ficou clara? "
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio.",
    "What caught your attention in this scene? Talk it over among yourselves. Is this scene "
    "clear? If you have any questions, ask me. If you have understood it, tell me and we will go "
    "to the rehearsal.",
)
_CLOSING_TAIL = (
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio.",
    "If you have any questions, ask me. If you have understood it, tell me and we will go to the "
    "rehearsal.",
)
_TO_THE_RED_MICROPHONE = (
    _her(
        r"(?<!\bque\s+(voc[êe]s\s+)?)(?<!\p{L})(toquem|apertem|cliquem)(?!\p{L})"
        r"(?:(?!\bn[ãa]o\b)[^.!?]){0,30}?\bmicrofone vermelho"
    ),
    _her(
        r"(?<!\b(you|they|we|I)\s+)(?<!\p{L})(tap|press|touch|click)(?!\p{L})"
        r"(?:(?!\bnot\b)[^.!?]){0,30}?\bred microphone"
    ),
)


def _ends_with(text: str, lines: tuple[str, ...]) -> bool:
    return _fold(text).endswith(lines)


def _calls_to_rehearse(text: str) -> bool:
    return _FENCE_CLOSES.search(text) is not None or any(
        instruction.search(text) for instruction in _TO_THE_RED_MICROPHONE
    )


def _left_part_open(earlier_guides: list[str]) -> bool:
    for earlier in reversed(earlier_guides):
        if _ends_with(earlier, _CLOSING_TAIL):
            return True
        if _FENCE_OPENS.search(earlier):
            return False
    return False


def _part_opening_faults(guide: str) -> list[str]:
    faults = []
    if not _ends_with(guide, _PART_CLOSING):
        faults.append(
            "the part opening does not end with the fixed closing ('O que chamou a atenção de "
            "vocês nessa cena? … a gente vai pro ensaio.')"
        )
    if _FENCE_OPENS.search(guide):
        faults.append("the fenced block was given in the same turn that opens a part")
    elif _calls_to_rehearse(guide):
        faults.append(
            "the part opening sent the team to rehearse ('Agora podem ensaiar.' or the red "
            "microphone) before the team said it was ready"
        )
    return faults


def _take_up_faults(guide: str, *, tail_owed: bool) -> list[str]:
    faults = []
    if tail_owed and not _ends_with(guide, _CLOSING_TAIL):
        faults.append(
            "the reply to the team's comment or question does not end with the closing's last "
            "two sentences ('Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e "
            "a gente vai pro ensaio.')"
        )
    if _FENCE_OPENS.search(guide):
        faults.append("the fenced block was given before the team said it was ready")
    elif _calls_to_rehearse(guide):
        faults.append(
            "the reply to the team's comment or question sent the team to rehearse ('Agora podem "
            "ensaiar.' or the red microphone) before the team said it was ready"
        )
    return faults


_THE_MAP = _her(r"\bo mapa\b|the map\b")
_FAREWELL = _her(r"vão com deus|god bless|amém|amen\b")


def mechanical_checks(
    *,
    guide: str,
    outcome: str,
    expect: dict[str, Any],
    previous_guide: str,
    earlier_guides: list[str],
) -> list[str]:
    """Every fault of one turn the runner can name without a judge, in her words and order.

    A keyed check is applied only where her script carries the key: a rehearsal invited is
    the demo failure on the turn where the team asked to understand first, and the voice's
    own send-off everywhere else. The three unkeyed ones — a verbatim repeat, `o mapa`, a
    blessing — are faults on any turn of any session.
    """
    fails: list[str] = []
    if expect.get("no_fail_safe") and outcome == "fail_safe":
        fails.append("fail_safe voiced in reply to a turn that must be answered")
    if guide.strip() and guide.strip() == previous_guide.strip():
        fails.append("verbatim repeat of the previous guide turn")
    if expect.get("no_rehearsal_invite") and _rehearsal_invited(guide):
        fails.append("rehearsal invited on a turn where the team asked to understand first")
    if expect.get("no_pairing") and _pairing_voiced(guide):
        fails.append("possible Ruth↔Mahlon pairing voiced (judge must confirm)")
    if expect.get("send_off_record") and not _RECORD.search(guide):
        fails.append("send-off did not tell the team to record (gravem o ensaio)")
    if expect.get("offers_choice") and not _offers_choice(guide):
        fails.append(
            "guide did not offer the choice (contar de novo OU seguir pra gravação) on a second "
            "near-complete telling"
        )
    if expect.get("no_choice_offer") and (
        _THE_RECORDING_AS_A_ROAD.search(guide) or _offers_choice_final(guide)
    ):
        fails.append("guide offered the recording as an alternative on a FIRST imperfect telling")
    for detail in expect.get("send_off_names") or []:
        if not _her(detail).search(guide):
            fails.append(
                "send-off did not repeat the detail the team carries into the recording: "
                f"/{detail}/i"
            )
    if expect.get("send_off_scene_by_scene") and not _SCENE_BY_SCENE.search(guide):
        fails.append("send-off did not tell the team to record scene by scene")
    if expect.get("accepts_telling"):
        refused = _SENT_BACK.search(guide) or _THE_NOUN_DEMANDED.search(guide)
        if refused:
            fails.append(
                "a faithful telling in other words was not accepted (meaning, not form): "
                f'"{refused[0]}"'
            )
    if expect.get("fenced_rehearsal"):
        fails.extend(_fence_faults(guide))
    if expect.get("part_opening_closing"):
        fails.extend(_part_opening_faults(guide))
    if expect.get("take_up_closing") or expect.get("take_up_closing_if_open"):
        tail_owed = bool(expect.get("take_up_closing")) or _left_part_open(earlier_guides)
        fails.extend(_take_up_faults(guide, tail_owed=tail_owed))
    if expect.get("offers_choice_final") and not _offers_choice_final(guide):
        fails.append(
            "guide did not offer the choice (ensaiar esta cena mais uma vez OU seguir e acertar no "
            "Ensaio Final)"
        )
    if _THE_MAP.search(guide):
        fails.append("says 'o mapa' / 'the map' to the team")
    if _FAREWELL.search(guide):
        fails.append("religious farewell of its own")
    return fails
