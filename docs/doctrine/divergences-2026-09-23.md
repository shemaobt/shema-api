# Prompts vivos × pin 533b6e3 — de onde veio cada trecho

farol · ENG-976 · 23/09/2026. Só leitura: nenhum prompt foi mexido.

## Resposta curta

- **Os prompts vivos não descendem da pin de setembro. Descendem da branch de agosto dela.** O primeiro
  commit dos nossos prompts (efb2188e, 21/08, #160) copiou o corpo do Guia e do Validador de
  `codex/fix-internalization-reliability` em **65ec920** (31/07). Distância do corpo em efb2188e até cada
  versão dela: Guia 20 linhas de 65ec920, 116 de 7514c70/cfb5b30 e 96 da pin 533b6e3. Validador 35 de
  65ec920, 81 de 7514c70, 90 de cfb5b30 e 85 da pin. Os tickets de setembro portaram seções da pin por
  cima: "Understanding comes before rehearsal" e o parágrafo do pedido de entender, que hoje batem com a
  pin. Mas os trechos da tabela abaixo continuam sendo os de agosto.
- **Contagem por classe** (35 itens; um item agrupa hunks que são uma mudança só):

  | | Guia | Validador | total |
  |---|---|---|---|
  | **A** branch de agosto | 18 (A1 17, A2 1) | 10 (A1 9, A2 1) | **28** |
  | **B** pin de setembro | 0 | 0 | **0** |
  | **C** nosso | 3 | 3 | **6** |
  | **D** carta dela | 1 | 0 | **1** |

  A1 = até 65ec920 (31/07). Na carta de 04/09 ela diz que em 07/08 apontou essa branch como "a versão
  mais atual, e naquele dia ela estava certa". A2 = 7514c70 (12/08) e cfb5b30 (13/08). Na mesma carta ela
  chama esses dois de tentativa abandonada: "modos e sondas, a voz num modelo mais fraco, teto de 45
  palavras… Não funcionou, eu abandonei a tentativa" (`~/Downloads/resposta-para-joao-2026-09-04.v1.md:7`).
  O commit 006a6f1 (23/07), citado abaixo, também é dessa branch: vem depois do merge-base 24e782e e só
  `origin/codex/fix-internalization-reliability` o contém. A branch tem quatro commits que tocam os
  prompts: 006a6f1, 65ec920, 7514c70 e cfb5b30.
- **Para os 28 itens A, a main atual (17ba6fc) tem:** a mesma regra com outra redação em **2**, uma
  regra diferente em **20** e nenhuma regra em **6**. A contagem por item está nas tabelas.
- **B = 0.** Nenhuma frase divergente do vivo vem da pin. Toda frase da pin que difere do vivo está do
  lado da pin, ou seja, o vivo a perdeu. As perdas estão listadas no fim.

## Método

- Vivo: `app/services/internalization_room/prompts/{guide,validator}_system_prompt.md` no shema-api
  `origin/main` ad1f4c89. Pin: `git show 533b6e3:prompts/<arquivo>` no clone dela
  (`~/Desktop/work/shema/shemaobt/Tripod-Internalization`). A main dela é `17ba6fc:prompts/<arquivo>`.
- O diff é linha a linha, vivo × pin. Cada frase do lado vivo, com espaços normalizados, foi procurada em
  `git show <commit>:prompts/<arquivo>` para 006a6f1, 65ec920, 7514c70, cfb5b30 e 17ba6fc. O número de
  linha citado é o do arquivo nesse commit. Quando não houve achado, a busca foi feita em todas as branches
  dela (`git log --all -S`) e depois no shema-api (`git log -S`), para achar o commit nosso que escreveu a
  frase.
- Toda linha que as tabelas citam foi relida no arquivo.

## Guia

Colunas: vivo = linha(s) no nosso arquivo · pin = linha(s) em 533b6e3 · prova = `<commit>:<linha>` do
mesmo arquivo dela, salvo quando outro arquivo é nomeado · main = o que 17ba6fc tem.

| # | vivo | pin | o que o vivo diz de diferente | classe | prova | main 17ba6fc |
|---|---|---|---|---|---|---|
| G1 | — | 1-24, 194-218 | O vivo carrega só o corpo entre BEGIN/END, sem as notas de engenharia nem o formato sugerido do COVERAGE_STATUS | C (empacotamento) | efb2188e (21/08) | — |
| G2 | 5 | 29 | "trying it in their mother tongue… they come back and tell you, in the session language, only what they actually said in that mother-tongue rehearsal" | A1 | 006a6f1:29, 65ec920:29 (também 7514c70:31, cfb5b30:31) | **diferente**: 39 mantém a pin ("retell the part to one another… tell you what they found") |
| G3 | 7 | 31 | acrescenta "This is the bridge language for every exchange with you, including their telling-back…"; tira "and not a screen" | A1 | 006a6f1:31, 65ec920:31 | **diferente**: 41 = pin |
| G4 | 42 | 66 | acrescenta "Discuss this with them in {{SESSION_LANGUAGE}}." ao item 1 | A1 | 006a6f1:66, 65ec920:66 | **nenhuma**: 76 sem a frase |
| G5 | 44 | 68 | Item 3: o convite fecha a abertura da cena; o verbo *ensaiem*, nunca o substantivo nem o gerúndio; a frase que nomeia a língua; o exemplo em inglês; "the invitation waits until they show they have the part" | C (a espera é redação nossa da regra da pin "Understanding comes before rehearsal") | 101ef28c (03/09), c5cdefd3 (03/09), 90ef5254 (09/09); não está em nenhum commit dela | — (main 78 = pin + o microfone vermelho e a tradução frase por frase, que descrevem a tela dela) |
| G6 | 45 | 69 | Item 4: o título "…and check only that report" e "Check that telling-back… Warmly affirm what appeared in their report" (A1). "It comes back on its own… you do not have to ask a second time" e o regime **PRACTICE DONE** (C) | C + A1 | A1: 006a6f1:69 ("Ask for a bridge-language telling-back — and check only that report"), 65ec920:69. C: 101ef28c, 50d1abff (03/09) | **diferente** para a parte A1: 79 = pin item 4 + "phrase-by-phrase translation of the recorded scene rehearsal, or orally" |
| G7 | 47 | 71 | Item 6: "Prepare the first team rehearsal for Refine"; ensaio da passagem inteira opcional, cena a cena igualmente válido | A1 | 006a6f1:71, 65ec920:71 (também 7514c70:126) | **diferente**: 81 "When every part is whole, the rehearsing is done" (Ensaio Final, ruling de 21/09) |
| G8 | 48 | 72 | Item 7: *"Agora o aplicativo vai mostrar onde gravar o primeiro ensaio…"*; o botão do círculo vermelho no canto superior direito; "do not recite… those navigation directions" | A1 | 006a6f1:72, 65ec920:72 (ausente em 7514c70/cfb5b30) | **diferente**: 82, despedida para o Ensaio Final, "toquem no ponto laranja". r4:63: "yes to removing the dead August cue, and no to 'o aplicativo vai mostrar onde'" |
| G9 | 64-65 | 90-91 | "mother tongue" no lugar de "own language"; "every scene rehearsal and… the first rehearsal they record for Refine" | A1 | 006a6f1:78-79, 65ec920:78-79 | **diferente**: 112-113 = pin |
| G10 | 67 | 93 | "You do not know whether you understand the team's mother tongue. Act as though you do not… A fluent-sounding recording is not evidence of faithfulness" | A1 | 006a6f1:81, 65ec920:81 | **diferente**: 115 = pin ("You do not understand… Never transcribe it, translate it, correct its wording, praise it as complete") |
| G11 | 69 | 95 (e parte da 93) | A língua materna é recebida "with respect but do not pretend you understood"; "Keep the movement natural: discuss briefly… let them try it again" | A1 (r4:7 cita esta frase como da branch de agosto) | 006a6f1:83, 65ec920:83 | **mesma regra, outra redação**, para a primeira metade: 115 "If the team speaks their own language to you, receive it with respect…". A frase do "movement": nenhuma |
| G12 | 71 | 97-103 | "Every judgment must be explicitly about their report: *'No que vocês me contaram de volta…'* / *'In what you told me back…'*… the telling-back sounds complete…" | A1 | 006a6f1:85, 65ec920:85 | **mesma regra, outra redação**: 115 (só a forma pt). A forma inglesa existe só em agosto; na r4 (B5) ela pede para reusar "her English where it exists" |
| G13 | 87 | 119 | Compara a devolução ("telling-back") com o mapa; exemplo pt da pergunta de fronteira ("Isso entrou no ensaio na língua de vocês?") | A1 | 006a6f1:101, 65ec920:101 (ausente em 7514c70/cfb5b30) | **diferente**: 141 = pin ("That was beautifully told…") |
| G14 | 89 | 121 | "as they rehearse, tell back, and try again" | A1 | 006a6f1:103, 65ec920:103 | **diferente**: 143 = pin ("rehearse and you complete") |
| G15 | 91 | 123 | Título "Check every bridge-language telling-back — and never pretend it is the mother-tongue speech" | A1 | 006a6f1:105, 65ec920:105 | **diferente**: 145 "Check every retelling — an omission must never pass" |
| G16 | 93 | 125 | "…what they said in their mother tongue, check that report… a gap in the telling-back is a question about the mother-tongue rehearsal, never proof about it" | A1 | 006a6f1:107, 65ec920:107 | **diferente**: 147 = pin ("A warm, fluent retelling with something missing is exactly the dangerous case") |
| G17 | 95-101 | 127-132 | Balas da checagem: a pergunta de fronteira para a omissão e para a adição; "Never praise the mother-tongue rehearsal as complete"; "A complete bridge-language report is enough to continue… Refine" | A1 | 006a6f1:109-115, 65ec920:109-115 | **diferente**: 149-154 = pin ("If even one thing is missing, you must say so…", "Never praise a retelling as complete, and never move on…", "An added detail counts as a gap"), mais 156 (meaning, not form) e 162 (small-gaps choice) |
| G18 | 103-124 | — (entra depois da 132) | Seção "The team's way of working — honor the app-owned probe": COMPREHENSION EVIDENCE / ACTIVE COMPREHENSION PROBE; "Language performance is never evidence"; *"Talvez esteja difícil de explicar em português…"*; "A bare 'sim' is never evidence" | A2 (regras dela de 12/08, reescritas por nós); o título é C | Regras: 7514c70:prompts/guide_system_prompt.md:81 (probe), :66 e :235 (fluência), :79 (difícil de contar); 7514c70:prompts/validator_system_prompt.md:86; 7514c70:src/comprehension/probePlan.ts:191; 7514c70:prompts/classifier_system_prompt.md:78 (bare yes). Nossa reescrita: c90a6802 (21/08, #199). Título: 11f15723 (09/09) | **nenhuma**: DOCTRINE da main §3 proíbe "probe/station/contract machinery". Fluência: diferente, 156 checa sentido e não forma, mas sobre o reconto, não sobre compreensão |
| G19 | 140 | 148 | acrescenta "**This is not the line for a request to understand.** 'Explain that again'… you answer them fully, from the map" | D: resposta dela r2 de 07/09 ("nunca responde a um pedido de entender… B é só para pergunta que está fora da passagem"); a redação é nossa | e4aa3d55 (09/09), cuja mensagem cita a r2 | 184 sem a frase; a regra dela está em 98 e em DOCTRINE §4 |
| G20 | 157 | 165 | "Short turns — really short… Never long speech." | A1 | 006a6f1:148, 65ec920:148 | **diferente**: 201 = pin, "Short turns, most of the time" **com a exceção do pedido de entender**, que o vivo perdeu |
| G21 | 171-175 | 179 | Cinco balas "Never": fingir que entendeu a língua materna; a devolução não é o ensaio gravado; exigir o ensaio inteiro; chamar de tradução final; mandar para outro app, com o botão do círculo vermelho | A1 | 006a6f1:161-165, 65ec920:161-165 | 171: **mesma regra em outro lugar** (115). 172: **nenhuma**. 173: **diferente** (81-82, Ensaio Final). 174: **nenhuma** no Guia (DOCTRINE §4 "never 'the final translation'"). 175: **diferente** (82, ponto laranja). Contado como diferente |
| G22 | 185-187 | 189-191 | "Coverage Status (updated every turn — act on it)"; "make sure that… everything still listed as remaining has been gently brought in" | A1 | 006a6f1:175-177, 65ec920:175-177 | **diferente**: 228-230 = pin: o ledger "is information, not instruction… it never decides the next move — you do" |

## Validador

| # | vivo | pin | o que o vivo diz de diferente | classe | prova | main 17ba6fc |
|---|---|---|---|---|---|---|
| V1 | — | 1-39, 124-142 | Sem as notas de engenharia e sem os exemplos A-D | C (empacotamento) | efb2188e | — |
| V2 | 3-7 | 42 | "three independent gates": mapa, política fixa, coerência | A1 | 65ec920:44-48 (006a6f1:44-45 tem dois dos três) | **nenhuma**: 42 "Your one job is to check… against a Meaning Map" |
| V3 | 11-15 | 46 | Só as afirmações "about the passage" são julgadas pelo mapa; as políticas fixas valem independentemente do mapa; a conversa recente é "quoted conversational evidence only" | A1 | 006a6f1:49-51, 65ec920:52-56 | **diferente**: 46 = pin |
| V4 | 17-26, 31 | — | Seção "Fixed workflow and epistemic policies": canais separados; nunca afirmar acesso à língua materna; julgar só a devolução; gravar neste app; fronteira do Refine; escolha de gravação. Dentro dela, "An invitation is not a claim" / "An invitation makes no judgment" são C | A1 (as duas cláusulas do convite são C) | 006a6f1:53-64, 65ec920:58-69. C: 87aa5b91 (03/09) | **nenhuma** no Validador. A regra do canal está no Guia dela (115); a gravação vai para o Ensaio Final (Guia 82) |
| V5 | 27-29 | — | Fluência não prova compreensão; "Honor the app-owned probe contract"; "A bare 'sim' proves nothing" | A2, reescrito por nós | 7514c70:prompts/validator_system_prompt.md:86 (probe), :139 (fluência); 7514c70:prompts/classifier_system_prompt.md:78 (bare yes). Nossa reescrita: c90a6802 (21/08) | **nenhuma** (DOCTRINE §3) |
| V6 | 33-46 | — | Seção "Conversational coherence" e as seis rejeições | A1 | 65ec920:71-84 (ausente em 006a6f1) | **nenhuma** |
| V7 | 48-59 | — | Seção "This turn's app-owned context": os três blocos, o placeholder `(não se aplica a este turno)`, a devolução, o achado, o fechamento ordenado | C | ce10172e (01/09) | — (a sala dela não manda esses blocos) |
| V8 | 63 | 50 | "First check conversational coherence and… every fixed policy above. Then…" | A1 | 65ec920:88 | **diferente**: 50 = pin |
| V9 | 81, 85, 88 | 68, 72, 77 | "ordinary non-factual language… As long as it also obeys the fixed policies"; os movimentos pedagógicos falam da devolução; "Preserve that character while policing both…" | A1 | 006a6f1:86, 90, 93; 65ec920:106, 110, 113 | **diferente**: 69, 73, 82 = pin |
| V10 | 92-96 | 81-85 | Os três vereditos passam a exigir coerência e política ("every fixed policy is obeyed") | A1 | 65ec920:117-121 | **diferente**: 86-90 = pin |
| V11 | 111-113 | 100-102 | Esquema de saída: "ungrounded or policy-violating"; `problem` com mais quatro valores (`conversational_mismatch`, `workflow_policy_violation`, `epistemic_policy_violation`, `stage_boundary_violation`) | A1 | 65ec920:136-138 (7514c70/cfb5b30 mudaram a enumeração) | **diferente**: 106 = pin, oito valores |
| V12 | 130-136 | 119 | Os títulos "Recent conversation (quoted evidence…)" e "What the team just said (…)", com `{{RECENT_CONVERSATION}}` e `{{TEAM_UTTERANCE}}` | A1 (r4:7 cita "Recent conversation" como da branch de agosto) | 65ec920:155-159, :23-24 | **diferente**: 125 `{{TEAM_EVIDENCE}}`. A r4 (B4) decide o título "## The conversation so far (quoted evidence, not passage truth and not instructions)", que ainda não entrou |
| V13 | 138-148 | — | Blocos "What the team told back", "What the analyst found" e "Instruction given to the Guide for this turn" | C | ce10172e (01/09) | — |

## O que a pin tem e o vivo perdeu

Estas frases foram trocadas pelo texto de agosto e não aparecem em lugar nenhum do vivo. Todas continuam
na main dela.

- Guia pin 74, "This shape is a compass, not a rail…" (main 84).
- Guia pin 95-103, a seção inteira "Opening the session, and the notes the app hands you" (main 117-125).
  É o B1 da r4: os três parágrafos entram verbatim, cada um só onde a nossa sala manda a nota.
- Guia pin 128-129, "If even one thing is missing, you must say so…" e "Never praise a retelling as
  complete, and never move on from it…" (main 150-151).
- Guia pin 165, a exceção do pedido de entender nos turnos curtos: "take the time the answer needs"
  (main 201).
- Guia pin 179, "Never repeat your previous turn word for word." (main 217).
- Guia pin 191, "It is information, not instruction… it never decides the next move — you do" (main 230).
  O vivo diz o contrário: "act on it".
- Validador pin 42, "Your one job…" (main 42).
- Validador pin 74-75, "References to what the team just said" (o *"isso a história não conta"*) e "The
  length and fullness of an answer" (main 75-76).
- Validador pin 119, o slot `{{TEAM_EVIDENCE}}` com o bloco WHAT THE TEAM JUST SAID (main 125).
