-- A session and three raised hands, so the inbox and the session list answer with something.
--
-- Without this the routes are all 200 and all empty: a client can check that it parses the
-- shape and nothing about what it draws. Coverage is the exception — it answers from the
-- canon and is already full — so what is seeded here is exactly what the database has to
-- carry: a session, and hands in the three states the inbox pages over.
--
-- The audio keys point at nothing. A card carries the address of a recording, and playing it
-- is a separate path (signed URLs, object storage) that a local database cannot stand in for;
-- what this seeds is every field the card is drawn from except the bytes.
--
-- `element_key` is a real key out of P01's Meaning Map, not an invented string. The inbox
-- resolves it against the catalogue to name the bead, so a made-up key would render exactly
-- like a question raised on no bead and prove nothing.
--
-- Idempotent, and takes the team from :team_name — pass it bare, as -v team_name=Equipe Piloto
-- is not bare enough; use -v team_name="Equipe Piloto" and let :'team_name' add the quotes.
insert into ir_sessions (id, pericope, status, messages, coverage_state, kept_takes,
                         back_translation, project_id, after_panorama)
select 'sessao-local-1', 'P01', 'in_progress', '[]', '{}', '[]', '{}', p.id, false
from projects p
where p.name = :'team_name'
  and not exists (select 1 from ir_sessions where id = 'sessao-local-1');

insert into ir_questions (id, device_id, session_id, pericope, audio_key, status,
                          project_id, element_key, duration_ms, transcript, created_at)
select 'pergunta-local-1', 'tablet-da-sala', 'sessao-local-1', 'P01',
       'ir/local/pergunta-1.m4a', 'open', p.id, 'being:B3', 4200,
       'por que ela volta para Belem se nao tem ninguem la', now() - interval '8 minutes'
from projects p
where p.name = :'team_name'
  and not exists (select 1 from ir_questions where id = 'pergunta-local-1');

insert into ir_questions (id, device_id, session_id, pericope, audio_key, status,
                          project_id, element_key, duration_ms, transcript, created_at)
select 'pergunta-local-2', 'tablet-da-sala', 'sessao-local-1', 'P01',
       'ir/local/pergunta-2.m4a', 'open', p.id, 'object:O1', 3100,
       'a fome durou quanto tempo', now() - interval '3 minutes'
from projects p
where p.name = :'team_name'
  and not exists (select 1 from ir_questions where id = 'pergunta-local-2');

-- One already answered and already heard, so the Desk has a card in the settled state too.
insert into ir_questions (id, device_id, session_id, pericope, audio_key, status,
                          reply_audio_key, answered_at, heard_at,
                          project_id, element_key, duration_ms, transcript, created_at)
select 'pergunta-local-3', 'tablet-da-sala', 'sessao-local-1', 'P01',
       'ir/local/pergunta-3.m4a', 'answered',
       'ir/local/resposta-3.m4a', now() - interval '20 minutes', now() - interval '15 minutes',
       p.id, 'scene:1', 5600, 'quem sao os quatro que saem de Belem',
       now() - interval '40 minutes'
from projects p
where p.name = :'team_name'
  and not exists (select 1 from ir_questions where id = 'pergunta-local-3');
