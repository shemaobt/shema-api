# Sala de Internalização (servidor)

O lado do servidor da Sala: guarda o que a equipe grava, conduz a retrotradução, chama o analista para conferir o que foi contado contra o Mapa de Sentido, resolve cada achado num endereço e decide como a fala do veredito termina. O app do tablet e a Mesa são os clientes.

## Language

### Vozes e papéis

**Guia** (`guide`):
A persona que conduz a conversa com a equipe durante toda a sessão, fora do veredito de retrotradução.
_Avoid_: narrador, condutor

**Falante** (`speaker`):
A persona que diz o veredito da retrotradução à equipe, mais quente que o analista. Um único papel.
_Avoid_: voice (nome interno alternativo), narrador falado, TTS

**Analista** (`analyst`):
A entidade que lê só os trechos contados e o Mapa de Sentido, nunca fala com a equipe e devolve apenas achados em JSON.
_Avoid_: verificador, revisor, classificador

**Validador** (`validator`):
A entidade que confere o rascunho de fala da Guia ou do Falante antes da síntese de áudio e pode recusá-lo, disparando a fala de segurança.
_Avoid_: analista (julga o conteúdo, não a fala)

**Verificador de correção** (`verify_correction`):
A chamada que confere se um conserto respondeu ao achado, contando os elementos que o trecho carregava, os que continuam ditos e os que a nova contagem trouxe de volta. Resolve e quebra são respostas independentes.
_Avoid_: analista, validador

**Equipe** (`project`):
O grupo de tradutores dono do trabalho. No schema a coluna chama-se `project_id`; a Mesa e o backlog dizem "equipe".
_Avoid_: team (nome antigo da coluna), usuário

**Mesa** (`desk`):
O app web do facilitador, consumidor das rotas de perguntas, paradas e sessões por equipe.
_Avoid_: painel, dashboard

**Sala** (`room`):
O sistema inteiro visto pela equipe: a composição de Guia, Falante, Analista e Validador. Metáfora de produto, não uma classe.
_Avoid_: bot, assistente

### Unidades de texto e áudio

**Perícope** (`pericope`):
O identificador da passagem bíblica, unidade de trabalho de uma sessão.
_Avoid_: passage (em prosa), texto

**Escopo** (`scope`):
O recorte da passagem conferido numa leitura do analista, que pode ser menor que a perícope.
_Avoid_: janela, trecho

**Take** (`take`):
Um arquivo de áudio gravado pela equipe, de um de dois tipos: ensaio (a passagem inteira na língua materna) ou retro (um pedaço contado na língua-ponte).
_Avoid_: gravação, áudio

**Língua materna** (`mother tongue`):
A língua da equipe, em que o ensaio é gravado e que ninguém no servidor entende.
_Avoid_: native, L1

**Língua-ponte** (`bridge language`):
A língua em que a equipe conta de volta, na qual o analista lê. O estado de calibração dessa língua é o `bridge_mode`.
_Avoid_: L2, português

**Segmento** (`segment`):
O objeto persistente e endereçável de um trecho contado: fatia de um take do ensaio, take de retro correspondente, transcrição, ordem e passe. Uma correção é uma linha nova que substitui a anterior, nunca uma edição. No app, o mesmo objeto chama-se trecho.
_Avoid_: chunk, stretch (prosa), trecho (nome do lado do app)

**Chunk** (`chunk`):
A posição numerada de um segmento na lista que o analista recebe numa leitura. Existe só durante a chamada; o servidor traduz o número em segmento.
_Avoid_: segmento, trecho

**Passe** (`pass_number`):
Quantas vezes um segmento foi contado: um na primeira contagem, dois quando recontado depois de um achado.
_Avoid_: tentativa, versão

**Contar de volta** (`telling back`):
O ato de dizer, na língua-ponte, o que um trecho da língua materna contém.
_Avoid_: traduzir, transcrever

**Não contado** (`untold`):
Um segmento gravado na língua materna que ainda não foi contado de volta. Não é um achado: só falta contar, e o analista não é chamado.
_Avoid_: faltante, pendente

**Ensaio** (`rehearsal`):
A gravação da passagem inteira na língua materna e a estação em que ela acontece. É para onde a equipe volta quando falta algo depois de tudo.
_Avoid_: rehearsal (em prosa), gravação

**Mapa de Sentido** (`meaning map`):
O conteúdo canônico da perícope contra o qual o analista compara, incluindo regras de preservação e o silêncio marcado que não se revela.
_Avoid_: gabarito, texto-base

**Colar** (`necklace`) e **conta** (`bead`):
A cobertura da passagem vista como um cordão de contas, cada conta um elemento do Mapa que passa por não encontrada, aflorada e engajada.
_Avoid_: progresso, checklist

**Panorama** (`panorama`):
A visão geral do livro falada antes da primeira passagem; uma sessão registra que veio logo depois dele para a Guia não se apresentar duas vezes.
_Avoid_: introdução

### Achados

**Achado** (`finding`):
A resposta do analista sobre um trecho contado: um tipo, uma nota e, quando há, um segmento. Os tipos: falta, adição, mudança de sentido, relação errada, evento reordenado, violação de preservação, evidência insuficiente, incerto.
_Avoid_: erro, problema

**Falta com endereço** (`missing` com `where` before ou inside):
Um elemento do Mapa ausente cujo lugar cabe num chunk existente. A equipe regrava e reconta aquele trecho.
_Avoid_: falta interna

**Falta sem endereço** (`missing` com `where` after no último chunk):
Um elemento ausente que fica depois de tudo o que foi contado. O segmento é nulo e a fala manda gravar mais e voltar ao ensaio, sem apagar nada.
_Avoid_: falta externa, missing null

**Onde** (`where`):
O campo de um achado de falta que diz se o conteúdo ausente fica antes, dentro ou depois do chunk citado.
_Avoid_: posição, offset

**Evidência suficiente** (`evidence_sufficient`):
A distinção entre "nenhuma diferença apareceu" e "pouco foi contado para conferir". Quando falsa, há sempre um achado de evidência insuficiente ou incerto nomeando o limite.
_Avoid_: confiança, score

**Aponta um trecho** (`points_at_a_stretch`):
A propriedade de um achado que põe um segmento específico na tela com os dois microfones. Decide o fechamento do veredito.
_Avoid_: tem endereço

### Correção e verificação

**Correção** (`correction`):
A retomada de exatamente um segmento, no lugar apontado pelo achado atual, para responder a ele. Detectada porque só uma posição da lista mudou.
_Avoid_: conserto (nome do lado do app para o mesmo gesto), fix, retell

**Reconto** (`retell`):
Cada nova contagem do mesmo trecho depois de um achado. No terceiro reconto a sala pede uma pessoa: um aviso, nunca um teto.
_Avoid_: tentativa, retry

**Substituída** (`superseded`):
Uma tentativa de contar de volta trocada por uma gravação nova. Seus achados viram histórico marcado, não desaparecem.
_Avoid_: apagada, descartada

**Conferida** (`checked`):
O estado em que a passagem foi contada e verificada por uma leitura inteira do analista e sai da roda para sempre. Verificações pontuais de correção nunca a produzem.
_Avoid_: concluída, done

**Ouviu o ensaio** (`playback_confirms_rehearsal`):
A evidência de que a equipe ouviu o ensaio inteiro, sobre o take vigente, antes de fechar.
_Avoid_: playback completo

### Fechamentos do veredito

**Fechamento** (`closing`):
Como o Falante termina o turno do veredito: devolvendo a escolha à tela, com uma pergunta, sem pergunta porque a passagem está conferida, pedindo resposta falada, ou mandando gravar mais e voltar ao ensaio.
_Avoid_: encerramento, outro

### Estados da sessão

**Sessão** (`session`):
O trabalho de uma equipe sobre uma perícope, com status em andamento, concluída ou precisa de pessoa.
_Avoid_: passagem, rodada

**Precisa de pessoa** (`needs_person`):
Uma parada, não um fim: viaja ao lado do status, nunca dentro dele, com o tipo bloqueante ou aviso.
_Avoid_: erro, falha, status

**Parada** (`halt`):
O motivo pelo qual a sala parou por uma pessoa: bloqueante ou aviso. Uma parada anterior à distinção lê-se como bloqueante.
_Avoid_: bloqueio, travamento

**Refine**:
A etapa posterior do produto que recebe o artefato da retrotradução. Não vive neste servidor.
_Avoid_: revisão, refinamento
