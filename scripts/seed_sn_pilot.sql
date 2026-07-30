-- The Sound Necklace pilot, taken from the dev database and replayed on top of the
-- production dump.
--
-- Production has the 49 acousteme artifacts of the Ruth pilot but none of the Sound
-- Necklace rows that make them reachable: sn_audio_refs is the only thing that binds a
-- standalone artifact to a project, and without it the project gate has nothing to stand
-- on. Those bindings were only ever created in the dev database, so a fresh production
-- dump does not carry them and never will.
--
-- The parent chain comes along because production has neither the pilot project nor its
-- language. Every statement guards itself — ON CONFLICT DO NOTHING, or NOT EXISTS on the
-- grant, which has no unique constraint to conflict on — so this is safe to replay and
-- safe to run against a database that already has any of it.
--
-- consent_present is false on every binding. It is the collection consent of PRD §12/O6,
-- asserted by a human who knows through seed_sn_audio_refs.py --consent; nobody recorded
-- it for these rows, and a seed file must not invent an agreement. The column is NOT NULL
-- with no server default, so false is written out rather than omitted.
--
-- The grant is keyed on is_platform_admin rather than on a person: list_user_projects
-- has no admin bypass, so without a project_user_access row the pilot is invisible in
-- every project list, and naming one address would leave everyone else with a project
-- they cannot open.
--
-- Written against the production schema, not dev's: the dev database carries columns
-- from unmerged branches (languages.is_active among them) that a restored dump has no
-- idea about. Regenerate from dev when the pilot changes; see the README.

INSERT INTO languages (id, name, code, created_at) VALUES ('eng', 'English', 'en', '2026-03-03 20:33:16.435141+00') ON CONFLICT (id) DO NOTHING;
INSERT INTO projects (id, name, description, created_at, updated_at, language_id) VALUES ('7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', 'Colar de Sons — Piloto', 'Projeto de teste local (ENG-247)', '2026-07-17 15:00:09.19089+00', '2026-07-23 21:39:55.992201+00', 'eng') ON CONFLICT (id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-1-promessa-da-vida-real', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-10-anos-fora-de-casa', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-10-assembleia-e-decisao-coletiva', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-11-direito-de-respiga', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-12-parente-protetor', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-13-viver-como-estrangeiro-residente', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-14-amor-leal-01', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-15-5-temas-principais', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-16-vocabulario', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-17-outros', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-19-de-abril', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-2-bencaos-faladas', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-3-lamentos', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-4-fala-formal-da-lideranca', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-5-alguem-em-posicao-superior', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-6-trabalho-agricula', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-7-parentesco', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-8-ir-embora-e-voltar-para-casa', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-9-fazer-mais-do-que-e-obrigado', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-a-bencao-que-a-mulher-recebeu', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-a-ida-na-fazenda', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-a-mandioca', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-a-menina-que-pai-rico', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-a-minha-maior-alegria', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-a-vida-dos-noivos-depois-do-casamento', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-a-volta-de-moises-para-o-egito', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-alegrei-quando-me-disseram', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-alianca', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-amizades-na-aldeia', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-aniversario', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-aqui-nao-e-meu-lar', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-as-frutas-na-aldeia', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-as-igrejas-da-minha-aldeia', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-as-pessoas-quando-voltam-para-aldeia', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-banho', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-bebe-recenascido', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-bendita', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-bezerro-na-fazenda', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-cancao-da-lacrimosa', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-carne-caca-e-a-forma-de-preparar', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-casamento', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-cicatriz', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-colheita-na-aldeia', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-como-era-a-vida-antigamente-na-aldeia', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-como-era-o-casamento-antes-e-como-e-agora', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-como-os-indios-faziam-com-os-forasteiro-querendo-judiar-das-mulheres-indiginas', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-como-plantar-mandioca', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-como-que-funciona-a-promessa', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;
INSERT INTO sn_audio_refs (audio_id, project_id, consent_present, created_at) VALUES ('ruth-como-que-plantamos-na-orta', '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', false, '2026-07-17 15:02:44.898281+00') ON CONFLICT (audio_id) DO NOTHING;

INSERT INTO project_user_access (id, project_id, user_id, role, granted_at)
SELECT gen_random_uuid()::text, '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc', u.id, 'manager', now()
FROM users u
WHERE u.is_platform_admin
  AND NOT EXISTS (
    SELECT 1 FROM project_user_access a
    WHERE a.project_id = '7ae3eca9-2747-4b3c-ba38-4f835f1b4bbc' AND a.user_id = u.id
  );
