-- One team for a facilitator to open, so the Desk has something to draw.
--
-- The routes answer 200 without it, with `serves_any_team: false` — enough to exercise the
-- contract and not enough to exercise the screen. This is the smallest thing that makes the
-- difference: a language, a project (which is what a team is, D-16), and the facilitator's
-- access to it.
--
-- Idempotent: running it twice inserts nothing the second time.
--
-- Takes the facilitator's email from :email — pass it as `-v email=someone@example.com`,
-- bare. The `:'email'` below is what adds the quotes; passing a value that already carries
-- them yields `''someone@example.com''`, which matches no row and reports success as
-- `INSERT 0 0`.
insert into languages (id, name, code)
select gen_random_uuid()::text, 'Ruth Piloto', 'rup'
where not exists (select 1 from languages where code = 'rup');

insert into projects (id, name, language_id)
select gen_random_uuid()::text, 'Equipe Piloto', l.id
from languages l
where l.code = 'rup'
  and not exists (select 1 from projects where name = 'Equipe Piloto');

insert into project_user_access (id, project_id, user_id, role)
select gen_random_uuid()::text, p.id, u.id, 'facilitator'
from projects p, users u
where p.name = 'Equipe Piloto'
  and u.email = :'email'
  and not exists (
    select 1 from project_user_access a where a.project_id = p.id and a.user_id = u.id
  );
