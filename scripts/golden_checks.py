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


_THE_RED_MICROPHONE = _her(r"microfone vermelho|red microphone")
_A_TELLING_BACK_ASKED = _her(
    r"me cont(em|a) em portugu|tell me (back )?in (english|portuguese)"
    r"|me contem o que vocês contaram"
)
_THE_ORANGE_DOT = _her(r"ponto laranja|orange dot")
_RECORD_AGAIN = _her(
    r"gravem (a passagem|o ensaio de vocês|o ensaio(?!\s+(da|desta|dessa)\s+cena))"
    r"|traduzam (a|essa|esta) gravação|record the (whole )?passage again"
    r"|record your rehearsal(?! of (this|that|the) scene)"
    r"|translate (the|your|this|that) recording"
)
_THE_WHOLE_PASSAGE_ASKED_FOR = _her(
    r"(?<!\b(eu|vou|I|I will|I'll|let me|going to)\s)(?<!\p{L})(contem|recontem|ensaiem|digam"
    r"|(querem|podem|conseguem|v[aã]o)\s+(me\s+)?(contar|recontar|ensaiar|dizer)"
    r"|vamos\s+(recontar|ensaiar)|tell|retell|rehearse)(?!\p{L})"
    r"(?:(?!\bcenas?\b|\bpartes?\b|\bscenes?\b|\bparts?\b)[^.?!]){0,60}?"
    r"(passagem inteira|passagem toda|história inteira|história toda|do começo ao fim"
    r"|whole passage|whole story|from (the )?beginning to (the )?end|from start to finish)"
)
_NO_RECORDING_YET = _her(r"n[ãa]o t[eê]m grava[çc][ãa]o|sem grava[çc][ãa]o|no recording")
_THE_STORY_DOES_NOT_TELL = _her(
    r"não conta|não diz|não fala|não está na história|não traz|não explica|não mostra|não revela"
    r"|não sabe(mos)? pela história|não vem da história|guarda (em )?silêncio"
    r"|fica (quieta|calada|em silêncio)|silêncio|de fora"
)
_RECALL_FRAME = _her(
    r"(?<!\p{L})lembr(em|am|a|ar|ando|aram)(?!\p{L})|(?<!\p{L})(na|da) última parte"
    r"|(?<!\p{L})(na|da) parte (anterior|de antes)"
    r"|(?<!\p{L})como vocês (já )?(sabem|viram|ouviram|lembram)|(?<!\p{L})remember(?!\p{L})"
    r"|(?<!\p{L})(in |from )?the last part|(?<!\p{L})(in |from )?the previous part"
    r"|(?<!\p{L})as you (already )?(know|heard|saw)(?!\p{L})"
)
_UNNEGATED = r"(?:(?!(?<!\p{L})(?:não|nunca|jamais|not|never|doesn't|does not)(?!\p{L}))[^.?!])"
_TELLS_AS_STORY = _her(
    rf"(?<!\p{{L}})a história\b{_UNNEGATED}{{0,20}}?(?<!\p{{L}})conta(?!\p{{L}})[^.?!]{{0,40}}?"
    rf"(?<!\p{{L}})que(?!\p{{L}})"
    rf"|(?<!\p{{L}})the story\b{_UNNEGATED}{{0,20}}?(?<!\p{{L}})tells(?!\p{{L}})[^.?!]{{0,40}}?"
    rf"(?<!\p{{L}})that(?!\p{{L}})"
)
_HER_FRAME_ON_AN_ELLIPSIS = _her(r"(?<!\p{L})(que|that)\s*(?:…|\.\.\.)\s+")
_THIS_PASSAGE = _her(
    r"(?<!\p{L})(nossa|nesta|nessa|esta|essa|desta|dessa) passagem(?!\p{L})"
    r"|(?<!\p{L})nossa parte(?!\p{L})|(?<!\p{L})(passagem|parte) de hoje(?!\p{L})"
    r"|(?<!\p{L})(our|this) passage(?!\p{L})|(?<!\p{L})our part(?!\p{L})"
    r"|(?<!\p{L})today's (passage|part)(?!\p{L})"
)
_OPENS_ON_NOW = _her(r"^\P{L}*(agora|now)(?!\p{L})")
_SAME_AS = _her(
    r"(?<!\p{L})mesm[ao]s?\s+(perguntas?|palavras?|coisas?|frases?|falas?)(?!\p{L})"
    r"|(?<!\p{L})(é|são|foi|foram)\s+(a|as|o|os)\s+mesm[ao]s?(?!\p{L})"
    r"|(?<!\p{L})the same (questions?|words?|things?)(?!\p{L})"
    r"|(?<!\p{L})(is|are|was|were) the same(?!\p{L})"
)
_PARAGRAPH_BREAK = _her(r"\n+")


def _sentences_of(text: str) -> list[str]:
    return _SENTENCE_END.split(_HER_FRAME_ON_AN_ELLIPSIS.sub(r"\1 ", text))


def _recall_of_unworked(text: str, marks: list[regex.Pattern[str]]) -> str | None:
    for sentence in _sentences_of(text):
        frame = _RECALL_FRAME.search(sentence)
        if not frame:
            continue
        for mark in marks:
            hit = mark.search(sentence)
            if not hit:
                continue
            between = sentence[min(frame.start(), hit.start()) : max(frame.start(), hit.start())]
            if not _TELLS_AS_STORY.search(between):
                return sentence.strip()
    return None


def _untold_mention_of_unworked(text: str, marks: list[regex.Pattern[str]]) -> str | None:
    for paragraph in _PARAGRAPH_BREAK.split(text):
        telling = False
        for raw in _sentences_of(paragraph):
            sentence = raw.strip()
            if not sentence:
                continue
            marked = any(mark.search(sentence) for mark in marks)
            if _TELLS_AS_STORY.search(sentence):
                telling = not _THIS_PASSAGE.search(sentence)
                continue
            if telling and any(
                back.search(sentence)
                for back in (_OPENS_ON_NOW, _THIS_PASSAGE, _RECALL_FRAME, _SAME_AS)
            ):
                telling = False
            if marked and not telling:
                return sentence
    return None


def _gap(negations: str, turns: str) -> str:
    return (
        rf"(?:(?!(?<!\p{{L}})(?:{negations})(?!\p{{L}})|,\s*(?:{turns})(?!\p{{L}})"
        rf"|(?<!\p{{L}})(?:e|and)\s+(?:vocês|you)(?!\p{{L}}))[^.!?;])"
    )


_GAP_PT = _gap(r"n[ãa]o|nem|nunca|jamais|nenhum|nenhuma|sem", r"e|mas|porém")
_GAP_EN = _gap(r"not|never|no|nor|without|doesn't|don't|isn't", r"and|but")
_MID = r"(?:\s+(?:mesma|mesmo|também|já|itself|also|already))?"
_THE_STORY_CONFIRMS = (
    _her(
        rf"(?<!\p{{L}})a própria (?:história|passagem){_GAP_PT}{{0,60}}?(?<!\p{{L}})"
        r"(?:sina(?:l|is)(?!\p{L})|confirm\p{L}*|comprov\p{L}*|mostra(?:ndo)?\s+isso(?!\p{L}))"
    ),
    _her(
        rf"(?<!\p{{L}})(?:história|passagem){_MID}\s+(?:dá|traz|mostra|deixa)\s+"
        r"(?:um\s+|uns\s+|o\s+|esse\s+)?sina(?:l|is)(?!\p{L})"
    ),
    _her(
        rf"(?<!(?<!\p{{L}})(?:se|que)\s+(?:a\s+)?)(?<!\p{{L}})(?:história|passagem){_MID}\s+"
        r"(?:confirma|comprova)(?!\p{L})"
    ),
    _her(
        rf"(?<!\p{{L}})the story itself{_GAP_EN}{{0,60}}?(?<!\p{{L}})"
        r"(?:signs?(?!\p{L})|confirm\p{L}*|prove\p{L}*|shows?\s+(?:this|that|it)(?!\p{L}))"
    ),
    _her(
        rf"(?<!\p{{L}})(?:story|passage){_MID}\s+(?:gives|shows|leaves)\s+(?:us\s+)?(?:a\s+)?"
        r"signs?(?!\p{L})"
    ),
    _her(
        rf"(?<!(?<!\p{{L}})(?:whether|if|that)\s+(?:the\s+)?)(?<!\p{{L}})(?:story|passage){_MID}"
        r"\s+(?:confirms|proves)(?!\p{L})"
    ),
)
_THE_TEAMS_QUESTION_ECHOED = (
    _her(
        r"(?<!(?<!\p{L})(?:n[ãa]o|se|nem)\s+)(?<!\p{L})é isso(?:\s+mesmo)?(?:\s+que)?"
        r"[\s,:—\u2013-]+a\s+(?:própria\s+)?(?:história|passagem)(?:\s+(?:tá|está|também|mesmo|já))?"
        r"\s+(?:mostra(?:ndo)?|confirma(?:ndo)?)(?!\p{L})"
    ),
    _her(
        r"^\s*(?:sim|é verdade|isso mesmo|é isso mesmo|exatamente|com certeza)(?!\p{L})"
        rf"{_GAP_PT}{{0,40}}?(?<!\p{{L}})(?:história|passagem)(?:\s+(?:tá|está|também|mesmo|já))?"
        r"\s+(?:mostra(?:ndo)?|confirma(?:ndo)?)\s+(?:isso|ess[ae]\s+esperança|uma\s+esperança"
        r"|esperança)(?!\p{L})"
    ),
    _her(
        r"(?<!(?<!\p{L})(?:not|if|whether)\s+)(?<!\p{L})that(?:'s|\u2019s|\s+is)\s+(?:exactly\s+|just\s+)?"
        r"what\s+the\s+(?:story|passage)(?:\s+itself)?\s+(?:is\s+)?(?:show(?:s|ing)|confirm(?:s|ing))"
        r"(?!\p{L})"
    ),
    _her(
        r"^\s*(?:yes|exactly|that's right|that is right|it's true|true)(?!\p{L})"
        rf"{_GAP_EN}{{0,40}}?(?<!\p{{L}})(?:story|passage)(?:\s+(?:itself|also|really))?\s+"
        r"(?:shows|confirms|is showing)\s+(?:this|that|it|that hope|this hope|hope)(?!\p{L})"
    ),
)
_ASKED = _her(r"\?\s*$")
_A_TAG_QUESTION = _her(r",\s*(?:né|não é|certo|right|isn't it)\?\s*$")


def _team_reading_confirmed(text: str) -> str | None:
    for sentence in _SENTENCE_END.split(text):
        for shape in _THE_STORY_CONFIRMS:
            if confirmed := shape.search(sentence):
                return confirmed[0]
        if _ASKED.search(sentence) and not _A_TAG_QUESTION.search(sentence):
            continue
        for echo in _THE_TEAMS_QUESTION_ECHOED:
            if echoed := echo.search(sentence):
                return echoed[0]
    return None


_SLEEP_OR_WAKE = _her(
    r"(?<!\p{L})(?:dorm(?:e|em|ia|iam|iu|indo|ido|ir)|adorme[cç]\p{L}*|sono"
    r"|acord(?:a|am|ou|ado|ada|ando|ava|ar|asse|aram)|acordá-lo|asleep|slept|sleep(?:s|ing)?"
    r"|wakes?|waking|woke|awoke|awake(?:ned|ns)?)(?!\p{L})"
)
_BOAZ = r"ele|o homem|o Boaz|Boaz|he|him|the man"
_SOMEONE_ELSE = (
    r"ela|a Rute|Rute|a mulher|a moça|a nora|a serva|a Noemi|Noemi|a sogra|eu|você|vocês|a gente"
    r"|nós|os moços|she|her|Ruth|the woman|Naomi|I|you|we"
)
_A_PERSON = _her(rf"(?<!\p{{L}})(?:({_BOAZ})|(?:{_SOMEONE_ELSE}))(?!\p{{L}})")
_BOAZ_RIGHT_AFTER = _her(rf"^\s*(?:{_BOAZ})(?!\p{{L}})")
_THE_STORY_DOES_NOT_SAY = _her(
    r"n[ãa]o (?:diz|fala|conta|explica|mostra|sabemos)(?!\p{L})|nunca (?:diz|fala|conta)(?!\p{L})"
    r"|sem dizer|não está (?:escrito|na história)|(?:does not|doesn't|never|not) (?:say|tell)"
)
_CARRIES_HIM = _her(r"-lo$")
_SONO = _her(r"^sono$")
_THE_ARTICLE_BEFORE = _her(r"(?<!\p{L})o\s+$")


def _boaz_sleeps_or_wakes(text: str) -> str | None:
    for sentence in _SENTENCE_END.split(text):
        for form in _SLEEP_OR_WAKE.finditer(sentence):
            before, after = sentence[: form.start()], sentence[form.end() :]
            if _THE_STORY_DOES_NOT_SAY.search(before):
                continue
            carries_him = (
                _CARRIES_HIM.search(form[0])
                or (not _SONO.search(form[0]) and _THE_ARTICLE_BEFORE.search(before))
                or _BOAZ_RIGHT_AFTER.search(after)
            )
            nearest = None
            for person in _A_PERSON.finditer(before):
                nearest = "boaz" if person[1] else "someone else"
            if carries_him or nearest != "someone else":
                return sentence[max(0, form.start() - 60) : form.end() + 30].strip()
    return None


_F1 = (
    "Vamos começar pela Familiarização. Primeiro eu conto a passagem inteira.",
    "Let's begin with Familiarization. First I will tell you the whole passage.",
)
_F3 = (
    "O que chamou a atenção de vocês nessa passagem? Conversem entre vocês. Se tiver alguma "
    "dúvida, me perguntem. Quando estiverem prontos, me digam e a gente vai pra Internalização da "
    "primeira cena.",
    "What caught your attention in this passage? Talk it over among yourselves. If you have any "
    "questions, ask me. When you are ready, tell me and we will move to Internalization of the "
    "first scene.",
)
_A_LATER_PART_OF_THE_BOOK = _her(r"quando (?:trabalharmos|a gente trabalhar) essa parte")
_A_SCENE_CALLED_PARTE = _her(
    r"(?<!\p{L})(?:primeira|segunda|terceira|quarta|quinta|sexta|sétima|oitava|próxima|essa"
    r"|nessa|dessa|esta|nesta|desta) parte(?!\p{L})"
    r"(?! d[oa] (?:livro|noite|dia|manhã|história)(?!\p{L}))"
)


def _familiarization_line_said(text: str) -> str | None:
    folded = _fold(text)
    if any(line in folded for line in _F1):
        return "first words (F1)"
    if any(line in folded for line in _F3):
        return "closing (F3)"
    return None


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
    if expect.get("invites_microphone"):
        if not _THE_RED_MICROPHONE.search(guide):
            fails.append("the Guide invited the rehearsal without the red-microphone instruction")
        if _A_TELLING_BACK_ASKED.search(guide):
            fails.append(
                "the Guide asked for an oral telling-back in the same turn as the microphone (two "
                "instructions at once)"
            )
    if expect.get("send_off_ensaio_final"):
        if not (_THE_ENSAIO_FINAL.search(guide) and _THE_ORANGE_DOT.search(guide)):
            fails.append(
                "send-off did not send the team to the Ensaio Final by the orange dot (Ensaio "
                "Final + ponto laranja)"
            )
        if _THE_RED_MICROPHONE.search(guide):
            fails.append(
                "send-off named the red microphone (the 2026-09-17 incident: the passage was "
                "recorded in the wrong place)"
            )
    if expect.get("no_record_again") and (again := _RECORD_AGAIN.search(guide)):
        fails.append(f'guide told the team to record or translate the passage again: "{again[0]}"')
    if expect.get("no_whole_retelling_request") and (
        whole := _THE_WHOLE_PASSAGE_ASKED_FOR.search(guide)
    ):
        fails.append(
            f'guide asked for the whole passage to be told or rehearsed again: "{whole[0]}"'
        )
    if expect.get("offers_choice_final") and not _offers_choice_final(guide):
        fails.append(
            "guide did not offer the choice (ensaiar esta cena mais uma vez OU seguir e acertar no "
            "Ensaio Final)"
        )
    if expect.get("send_off_names_unrecorded_scene") and not _NO_RECORDING_YET.search(guide):
        fails.append("send-off did not say that a part told only aloud has no recording yet")
    if expect.get("names_new_fact") and not _THE_STORY_DOES_NOT_TELL.search(guide):
        fails.append("guide did not name the new fact as something the story does not tell")
    if expect.get("no_recall_of_unworked"):
        marks = [_her(mark) for mark in expect["no_recall_of_unworked"]]
        if recalled := _recall_of_unworked(guide, marks):
            fails.append(
                "the voice recalled a passage this team has not worked yet as if the team knew it "
                f"('lembrem' / 'na última parte'): \"{recalled}\""
            )
        if expect.get("tells_as_story") and (untold := _untold_mention_of_unworked(guide, marks)):
            fails.append(
                "the voice spoke of a passage this team has not worked yet without 'a história "
                f'conta que…\': "{untold}"'
            )
    if expect.get("team_reading_stays_theirs") and (confirmed := _team_reading_confirmed(guide)):
        fails.append(
            "the team's reading was presented as the passage's own (the story confirms it, or "
            f'gives a sign of it): "{confirmed}"'
        )
    if expect.get("no_familiarization_lines") and (line := _familiarization_line_said(guide)):
        fails.append(
            f"the whole passage asked for mid-session was told with the Familiarization's {line} — "
            "D7 (a): without F1 and without F3, the moment unchanged"
        )
    if expect.get("scene_word_cena") and (
        parte := _A_SCENE_CALLED_PARTE.search(_A_LATER_PART_OF_THE_BOOK.sub("", _fold(guide)))
    ):
        fails.append(
            f'the voice called a scene of today\'s passage "parte" ("{parte[0]}") — D1 (c): "cena"'
        )
    if expect.get("boaz_never_asleep") and (asleep := _boaz_sleeps_or_wakes(guide)):
        fails.append(
            f'the voice made Boaz sleep or wake at the threshing-floor night: "{asleep}" — P09 R19 '
            "/ P10 R14: he lies down (3:7), trembles and twists (3:8); the text never says he "
            "slept or woke"
        )
    if _THE_MAP.search(guide):
        fails.append("says 'o mapa' / 'the map' to the team")
    if _FAREWELL.search(guide):
        fails.append("religious farewell of its own")
    return fails
