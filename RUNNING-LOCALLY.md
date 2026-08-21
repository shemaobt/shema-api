# Bringing the composed API up locally

The API the Desk can develop against does not exist on `main`: the facilitator routes live on
`integration/facilitator-api`, and until they land there is nothing for a client to be written
against. This is how to put that branch on a port, with a database, from nothing.

Everything here is disposable and on a high port. It does not touch a database or a container
that was already running — someone else's `tripod_db` on 5432 and `tripod_backend` on 8000 stay
exactly where they are. `docker compose` is deliberately not used: its `container_name` and its
5432 are fixed, so it collides with whatever is already up.

## 1. A worktree on the integration branch

```sh
cd ~/Documents/programming/obt/shema-api
git fetch --all --prune
git worktree add .worktrees/subir --detach origin/integration/facilitator-api
cd .worktrees/subir
```

Read the exit code of `git fetch` itself. A fetch that failed and a fetch that found nothing
new look the same in the command after it, and stale refs answer "no" to everything.

## 2. The database

```sh
docker run -d --name shema-integracao-db \
  -e POSTGRES_PASSWORD=integracao -e POSTGRES_USER=integracao -e POSTGRES_DB=integracao \
  -p 55432:5432 postgres:17

until docker exec shema-integracao-db pg_isready -U integracao -q; do sleep 1; done

docker network create shema-integracao
docker network connect shema-integracao shema-integracao-db
```

## 3. The API

```sh
docker build -f Dockerfile.dev -t shema-integracao-api .

docker run -d --name shema-integracao-api --network shema-integracao -p 8010:8000 \
  -e DATABASE_URL="postgresql+asyncpg://integracao:integracao@shema-integracao-db:5432/integracao" \
  -e JWT_SECRET_KEY="integracao-local-only" \
  -e INNGEST_DEV=1 \
  shema-integracao-api

until [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8010/docs)" = 200 ]; do sleep 2; done
```

The container migrates itself on boot, with `alembic upgrade heads` — plural. An integration
branch bifurcates its Alembic graph every time the chain composes again, and `head` refuses to
resolve while more than one exists, so the container would not boot at all. See the comment on
that line in `Dockerfile.dev` for why this weakens no gate.

## 4. A facilitator who gets through the gate

A database created from scratch registers the apps and their roles on the way up —
`internalization-room` and its `facilitator` role among them — so the facilitator path is
reachable without making anybody a platform admin.

```sh
curl -s -X POST http://localhost:8010/api/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"facilitadora@example.com","password":"integracao123","display_name":"Facilitadora Local"}'

docker exec -e DATABASE_URL="postgresql+asyncpg://integracao:integracao@shema-integracao-db:5432/integracao" \
  shema-integracao-api uv run python scripts/grant_app_role.py \
  facilitadora@example.com internalization-room facilitator
```

## 5. A team, or the Desk has nothing to draw

```sh
docker exec -i shema-integracao-db psql -U integracao -d integracao \
  -v email=facilitadora@example.com < scripts/seed_local_team.sql
```

Without it the routes still answer 200, with `serves_any_team: false` — the contract is
exercisable and the screen is not.

## 5b. Something for the inbox to hold

A team is enough for the routes to answer. It is not enough for them to answer with anything:
the inbox comes back empty and the session list comes back `[]`, so a client can check that it
parses the shape and nothing about what it draws. Coverage is the exception — it is answered
from the canon and is full from the start.

```sh
docker exec -i shema-integracao-db psql -U integracao -d integracao \
  -v team_name="Equipe Piloto" < scripts/seed_local_content.sql
```

One session and three raised hands — two open, one answered and heard — with transcripts,
durations and real element keys out of P01's Meaning Map. After it, `/facilitator/teams`
reports `open_hands_total: 2` and the inbox has three cards to draw.

The audio keys point at nothing. A card carries the *address* of a recording; playing it is a
separate path through signed URLs and object storage that a local database cannot stand in for.

## The email validator rejects more than you would guess

`@something.test` and `@something.local` are both refused with **422** — "a special-use or
reserved name that cannot be used with email" — and the message says `email`, not `password`,
which is easy to misread as a credential problem. `@something.example` is accepted. Measured,
not assumed.

## Do not reach for `scripts/seed_apps_roles.py`

It does not register the apps this needs. Its `SEED_APPS` list carries `tripod-studio`,
`meaning-map-generator`, `oral-bridge`, `oral-collector`, `avita`, `annotation-studio` and
`sound-necklace` — and **not** `internalization-room`, `project-health` or `translation-helper`.
Running it against a fresh database adds seven apps nobody here needs and none of the ones they
do.

The apps this procedure depends on arrive by migration, not by script:
`20260812_room04_register_internalization_room_app.py` is the one that registers the room and
its `facilitator` role. That is why a database created from nothing already has them.

## `/api/apps` is not the way to check whether apps exist

It answers **403** to anyone who is not a platform admin — it never reports an empty list for
lack of apps, and reading a refusal there as "nothing is registered" points at the environment
when the answer is about the caller.

The route that answers for the signed-in user is `GET /api/apps/my-apps`, and it returns what
*they* hold. An account with no role gets `[]` from it, which is a true statement about the
account and says nothing about the database. To ask the database, ask the database:

```sh
docker exec shema-integracao-db psql -U integracao -d integracao \
  -c "select app_key, is_active from apps order by app_key;"
```

## 6. The token, and a look

```sh
TOKEN=$(curl -s -X POST http://localhost:8010/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"facilitadora@example.com","password":"integracao123"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['tokens']['access_token'])")

curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8010/api/facilitator/teams
```

## Tearing it down

```sh
docker rm -f shema-integracao-api shema-integracao-db
docker network rm shema-integracao
git worktree remove --force .worktrees/subir
```

## What this gives you, and what it does not

Sixteen facilitator routes answer here, against **zero** on whatever is running on 8000. The
eight `GET`s among them answer **200** with a facilitator's credential and **401** without one,
on an account that is **not** a platform admin — checked, not assumed.

What is not covered:

- **The eight write routes** (`POST` / `PATCH` / `DELETE`) are unexercised. They need a paired
  device and a recorded question, and neither exists in a fresh database.
- **The database is new and empty.** No production dump, no real content: one team, one
  language, and whatever you create yourself.
- **Qdrant and BHSA do not come up**, and the log says so on boot. Neither is on the
  facilitator path; the API serves it regardless.
- **A database that already exists is a different story.** The local `tripod_db` predates the
  migration that registers `internalization-room`, so on *that* database the app is missing and
  the facilitator path is not reachable at all — only the platform-admin door is. That is a
  property of the old database, not of this procedure, and it is why this one starts from
  nothing. Reported by whoever hit it; not re-checked here, because that container belongs to
  someone else.
