# Sessões-ouro — 2026-09-16, esta sala em `87208b24`, `http://127.0.0.1:8048/api/internalization-room/text-seam/`

Rodada `2026-09-16T23-12-12` de `scripts/golden_runner.py` sobre os roteiros dela (roteiros e doutrina no pin `533b6e3` · cânon `7372ec0`): **4/5 aprovadas pelo juiz, 3 avisos mecânicos, 1 fail-safes em 40 turnos reais, 1 sessões recusadas.**

Este portão vale para o release, não só para o CI (DOCTRINE §5.2): nada que toque prompt, laço de turno, modelo ou tela chega à equipe sem as sessões-ouro aprovadas pelo juiz e sem aviso mecânico — uma suíte verde não basta para publicar uma mudança de prompt.

| Sessão | Juiz | Mecânico | Observação |
|---|---|---|---|
| J01-frame-before-elicit | — | recusada | 400 {"detail":"no vendored Meaning Map for J01","code":"BAD_REQUEST"} |
| P01-opening-and-mother-tongue | PASS | 1 | turn 3: fail_safe voiced in reply to a turn that must be answered |
| P01-retelling-gaps-and-additions | PASS | 2 | turn 6: possible Ruth↔Mahlon pairing voiced (judge must confirm); turn 11: send-off did not tell the team to record (gravem o ensaio) |
| P01-spoilers-and-boundaries | PASS | 0 |  |
| P01-understand-first | PASS | 0 |  |

Custo da rodada (linhas `[llm-usage]`, preços de tabela): ≈ US$ 7.03 — classifier US$ 0.49 · guide US$ 2.66 · judge US$ 1.17 · validator US$ 2.71.
Latência Guia+Validador por turno: 17 a 55 s (mediana ≈ 28 s); turno inteiro, com o classificador em linha: 0 a 62 s (mediana ≈ 30 s).

Primeira rodada com o juiz dela ligado (ENG-830): o prompt é `prompts/vendor/golden_judge_system_prompt.md` sem edição, em Fable 5.1 (a mesma escada da voz), com o mapa do Validador e a língua da sessão do mesmo pin. O veredito de cada sessão está ao lado do transcript, em `<sessão>.<carimbo>.verdict.json`. As quatro sessões que a sala tocou passam no juiz; a rodada sai 1 pela regra dela (juiz aprovou E zero avisos mecânicos), porque três avisos mecânicos ficam de pé e Jonas segue fora deste cânon. Comparação: o 5/5 dela de 03/09 custou ≈ US$ 8 (57 turnos) com mediana de 27 s; esta, ≈ US$ 7,03 em 40 turnos (juiz US$ 1,17 das quatro chamadas), mediana de 28 s.

O que o juiz disse dos dois avisos que a coluna mecânica manda confirmar: o par Rute↔Malom do turno 6 de `P01-retelling-gaps-and-additions` é o Guia corrigindo o pareamento que a equipe inventou, não o Guia pareando — `containment` 4, nenhum incidente de contenção; o fail-safe do turno 3 de `P01-opening-and-mother-tongue` não virou incidente do juiz (ENG-794 continua sendo a causa). O aviso novo, o fecho sem "gravem" no turno 11, o juiz também anotou (`no_record_close`, minor). Menores que o juiz anotou nas quatro, para a Marcia decidir se afina o prompt: recontagem declarada inteira antes de apontar a falta (turnos 4 e 9 de duas sessões); o Guia supre a lacuna em vez de mandar ensaiar de novo; "não fala de pecado" amplia um silêncio que o mapa marca só como ausência de ação divina; um turno repetido quase palavra por palavra quando a equipe pediu a parte seguinte (turno 5 de `P01-opening-and-mother-tongue`, major).
