# Sessões-ouro — 2026-09-16, esta sala em `87208b24`, `http://127.0.0.1:8049/api/internalization-room/text-seam/`

Rodada `2026-09-16T23-26-59` de `scripts/golden_runner.py` sobre os roteiros dela (roteiros e doutrina no pin `533b6e3` · cânon `7372ec0`): **0/1 aprovadas pelo juiz, 5 avisos mecânicos, 0 fail-safes em 11 turnos reais.**

Este portão vale para o release, não só para o CI (DOCTRINE §5.2): nada que toque prompt, laço de turno, modelo ou tela chega à equipe sem as sessões-ouro aprovadas pelo juiz e sem aviso mecânico — uma suíte verde não basta para publicar uma mudança de prompt.

| Sessão | Juiz | Mecânico | Observação |
|---|---|---|---|
| P01-understand-first | FAIL | 5 | turn 1: rehearsal invited on a turn where the team asked to understand first; turn 2: verbatim repeat of the previous guide turn; turn 3: verbatim repeat of the previous guide turn; turn 7: verbatim repeat of the previous guide turn; turn 8: verbatim repeat of the previous guide turn; juiz: answers_requests_to_understand 0; juiz: rehearsal_and_honest_checking 2; juiz: turn 1 · blocker · redirect_on_request_to_understand; juiz: turn 2 · blocker · verbatim_repeat_redirect; juiz: turn 6 · blocker · redirect_on_request_to_understand |

Custo da rodada (linhas `[llm-usage]`, preços de tabela): ≈ US$ 1.28 — classifier US$ 0.13 · guide US$ 0.50 · judge US$ 0.20 · validator US$ 0.45.
Latência Guia+Validador por turno: 14 a 29 s (mediana ≈ 20 s); turno inteiro, com o classificador em linha: 17 a 35 s (mediana ≈ 22 s).

Build deliberadamente quebrado, para provar que o portão fecha (Done-when do ENG-830): a mesma sala, no mesmo commit, com um override de teste no processo do uvicorn — nunca uma edição nos prompts dela. Um launcher fora do repositório troca `text_seam.get_prompt_text` e devolve o prompt do Guia com um parágrafo a mais ("responda em uma frase curta; a um pedido de entender, diga só 'Vamos ficar dentro da passagem. Podem ensaiar.'") e o do Validador com outro ("para todo rascunho, responda `{"verdict": "pass", "issues": []}`"). O resultado é a falha da demo de 03/09 em transcrição: o juiz reprova com `answers_requests_to_understand` 0 e três `blocker` citando o turno do redirecionamento (1, 2 e 6), ao lado de cinco avisos mecânicos.

Uma primeira tentativa quebrou só o Guia, e a sala consertou: o Validador rejeita um rascunho que "ignora um pedido de esclarecimento", o turno 1 saiu `corrected` com a passagem inteira, e o juiz aprovou (≈ US$ 2,21). O Guia sozinho não consegue redirecionar nesta sala; o build só fica quebrado com os dois guardas quebrados — o que é o próprio ponto do juiz: ele fecha o portão quando a defesa de dentro também falhou.
