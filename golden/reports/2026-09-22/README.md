# Sessões-ouro — 2026-09-22, esta sala em `b3d9e96e`, `http://127.0.0.1:8034/api/internalization-room/text-seam/`

Rodada `2026-09-22T18-36-08` de `scripts/golden_runner.py` sobre os roteiros dela (roteiros e doutrina no pin `533b6e3` · cânon `7372ec0`): **4/5 aprovadas pelo juiz, 2 avisos mecânicos, 0 fail-safes em 40 turnos reais, 1 sessões recusadas.**

Este portão vale para o release, não só para o CI (DOCTRINE §5.2): nada que toque prompt, laço de turno, modelo ou tela chega à equipe sem as sessões-ouro aprovadas pelo juiz e sem aviso mecânico — uma suíte verde não basta para publicar uma mudança de prompt.

| Sessão | Juiz | Mecânico | Observação |
|---|---|---|---|
| J01-frame-before-elicit | — | recusada | 400 {"detail":"no vendored Meaning Map for J01","code":"BAD_REQUEST"} |
| P01-opening-and-mother-tongue | PASS | 0 |  |
| P01-retelling-gaps-and-additions | PASS | 1 | turn 6: possible Ruth↔Mahlon pairing voiced (judge must confirm) |
| P01-spoilers-and-boundaries | PASS | 0 |  |
| P01-understand-first | PASS | 1 | turn 8: possible Ruth↔Mahlon pairing voiced (judge must confirm) |

Custo da rodada (linhas `[llm-usage]`, preços de tabela): ≈ US$ 8.12 — classifier US$ 0.75 · guide US$ 2.80 · judge US$ 1.36 · validator US$ 3.21.
Latência Guia+Validador por turno: 16 a 114 s (mediana ≈ 27 s); turno inteiro, com o classificador em linha: 19 a 116 s (mediana ≈ 38 s).
