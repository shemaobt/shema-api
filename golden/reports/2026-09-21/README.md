# Sessões-ouro — 2026-09-21, esta sala em `4f4cfc4f`, `http://127.0.0.1:8034/api/internalization-room/text-seam/`

Rodada `2026-09-21T20-08-34` de `scripts/golden_runner.py` sobre os roteiros dela (roteiros e doutrina no pin `533b6e3` · cânon `7372ec0`): **4/5 aprovadas pelo juiz, 2 avisos mecânicos, 0 fail-safes em 40 turnos reais, 1 sessões recusadas.**

Este portão vale para o release, não só para o CI (DOCTRINE §5.2): nada que toque prompt, laço de turno, modelo ou tela chega à equipe sem as sessões-ouro aprovadas pelo juiz e sem aviso mecânico — uma suíte verde não basta para publicar uma mudança de prompt.

| Sessão | Juiz | Mecânico | Observação |
|---|---|---|---|
| J01-frame-before-elicit | — | recusada | 400 {"detail":"no vendored Meaning Map for J01","code":"BAD_REQUEST"} |
| P01-opening-and-mother-tongue | PASS | 0 |  |
| P01-retelling-gaps-and-additions | PASS | 1 | turn 6: possible Ruth↔Mahlon pairing voiced (judge must confirm) |
| P01-spoilers-and-boundaries | PASS | 0 |  |
| P01-understand-first | PASS | 1 | turn 8: possible Ruth↔Mahlon pairing voiced (judge must confirm) |

Custo da rodada (linhas `[llm-usage]`, preços de tabela): ≈ US$ 7.91 — classifier US$ 0.75 · guide US$ 2.63 · judge US$ 1.40 · validator US$ 3.13.
Latência Guia+Validador por turno: 15 a 69 s (mediana ≈ 25 s); turno inteiro, com o classificador em linha: 16 a 84 s (mediana ≈ 37 s).
