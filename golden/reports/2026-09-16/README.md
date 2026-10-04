# Sessões-ouro — 2026-09-16, esta sala em `ec3dfbaf`, `http://127.0.0.1:8047/api/internalization-room/text-seam/`

Rodada `2026-09-16T21-13-26` de `scripts/golden_runner.py` sobre os roteiros dela (roteiros e doutrina no pin `533b6e3` · cânon `7372ec0`): **2/5 sem aviso mecânico (juiz ainda não ligado), 2 avisos mecânicos, 1 fail-safes em 40 turnos reais, 1 sessões recusadas.**

| Sessão | Juiz | Mecânico | Observação |
|---|---|---|---|
| J01-frame-before-elicit | — | recusada | 400 {"detail":"no vendored Meaning Map for J01","code":"BAD_REQUEST"} |
| P01-opening-and-mother-tongue | — | 1 | turn 3: fail_safe voiced in reply to a turn that must be answered |
| P01-retelling-gaps-and-additions | — | 1 | turn 6: possible Ruth↔Mahlon pairing voiced (judge must confirm) |
| P01-spoilers-and-boundaries | — | 0 |  |
| P01-understand-first | — | 0 |  |

Custo da rodada (linhas `[llm-usage]`, preços de tabela): ≈ US$ 6.51 — classifier US$ 0.49 · guide US$ 2.93 · validator US$ 3.09.
Latência Guia+Validador por turno: 14 a 54 s (mediana ≈ 28 s); turno inteiro, com o classificador em linha: 0 a 55 s (mediana ≈ 30 s).
