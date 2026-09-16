# Sessões-ouro — 2026-09-03 (noite), chave da Marcia, modelo claude-fable-5-1

Rodada completa das cinco sessões (`npm run golden`) sobre o tip `6b832a7` do ramo `fia/pilot-2026-09`:
**5/5 aprovadas pelo juiz, 0 avisos mecânicos, 0 fail-safes em 57 turnos reais.**

| Sessão | Juiz | Mecânico | Observação |
|---|---|---|---|
| J01-frame-before-elicit | PASS | 0 | reconto completo sob pedido; tempestade/marinheiros recusados sem spoiler |
| P01-opening-and-mother-tongue | PASS | 0 | a voz abre; Terena no mic vira nota, nunca palavras; interrupção respondida sem repetir |
| P01-spoilers-and-boundaries | PASS | 0 | Boaz recusado; par Rute↔filho recusado; Deus-e-a-fome como silêncio |
| P01-understand-first (a falha da demo de 2026-09-03) | PASS | 0 | "recontou a passagem inteira, passo a passo, sem redirecionar"; não fechou com lacunas |
| P01-retelling-gaps-and-additions | PASS | 0 | faltas e acréscimos nomeados a cada reconto; o fecho "gravem o ensaio… em Terena" veio quando a versão ficou inteira (2ª execução, após completar a versão final do roteiro — mudança de roteiro, não de prompt) |

Custo da rodada completa (linhas `[llm-usage]`, preços de tabela): ≈ US$ 8 — Fable 5.1 US$ 7,07 (Guia+Validador+juiz, 896 mil tokens do mapa servidos do cache) · Sonnet 5 US$ 0,90 (classificador).
Latência Guia+Validador por turno: 10–56 s (mediana ≈ 27 s). Um turno registrou 322 s no runner: 39 s de Guia+Validador, o resto o classificador de cobertura rodando em linha (no app ele roda fora do caminho da voz).

Menores anotados pelo juiz, para a Marcia decidir se afina o prompt: (1) "a história ainda vai chegar lá" ao ouvir Rute↔Boaz quase confirma o que veio de fora; (2) falta nomeada de forma vaga ("mais uma coisinha") em dois recontos; (3) uma vez mandou ensaiar o todo após uma abertura ainda rasa; (4) uma vez disse "está inteiro" antes de apontar a falta no mesmo turno.
