# Sessões-ouro — 2026-09-16, esta sala em `87208b24`, `http://127.0.0.1:8047/api/internalization-room/text-seam/`

Rodada `2026-09-16T23-11-09` de `scripts/golden_runner.py` sobre os roteiros dela (roteiros e doutrina no pin `533b6e3` · cânon `7372ec0`): **4/4 aprovadas pelo juiz, 2 avisos mecânicos, 1 fail-safes em 40 turnos reais.**

Este portão vale para o release, não só para o CI (DOCTRINE §5.2): nada que toque prompt, laço de turno, modelo ou tela chega à equipe sem as sessões-ouro aprovadas pelo juiz e sem aviso mecânico — uma suíte verde não basta para publicar uma mudança de prompt.

| Sessão | Juiz | Mecânico | Observação |
|---|---|---|---|
| P01-opening-and-mother-tongue | PASS | 1 | turn 3: fail_safe voiced in reply to a turn that must be answered |
| P01-retelling-gaps-and-additions | PASS | 1 | turn 6: possible Ruth↔Mahlon pairing voiced (judge must confirm) |
| P01-spoilers-and-boundaries | PASS | 0 |  |
| P01-understand-first | PASS | 0 |  |

Custo da rodada (linhas `[llm-usage]`, preços de tabela): ≈ US$ 0.72 — judge US$ 0.72.

Re-julgamento (`--rejudge golden/reports/2026-09-16`) das quatro transcrições que a rodada de 16/09 já tinha commitado sem juiz: a sala não foi tocada, só o juiz rodou, com o mapa e a língua do mesmo pin, e cada veredito leva o carimbo da transcrição que julgou. É a segunda vez que o build sem alteração reproduz o seu baseline — o Done-when do ENG-830 pede duas —, cumprida com uma rodada real (`2026-09-16-juiz`) e um re-julgamento, e não com duas rodadas reais, por custo: cinco sessões com juiz custam ≈ US$ 7, quatro vereditos custam ≈ US$ 0,72. As quatro passam aqui como passam lá; os avisos mecânicos são os que a rodada de 16/09 exportou. `--rejudge` é também o caminho para quando o prompt do juiz mudar sem a sala mudar. Uma primeira tentativa, com o teto de 4000 tokens do `run.ts` dela, custou US$ 0,97 e cortou um dos quatro vereditos no meio do JSON — o teto do juiz nesta sala é 16000 desde então.
