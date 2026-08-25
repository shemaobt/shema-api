# API request examples (.http)

Use these with VS Code [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) or JetBrains HTTP Client.

## Layout

- **api.http** – Full flow in one file: health → auth (login named) → roles. Token from login is reused for authenticated requests. Best for running the whole flow in order.
- **health.http** – Health check only.
- **auth.http** – Signup, login, refresh, logout, me, my-roles. Login is named so `me` / `refresh` / `logout` / `my-roles` in the same file use the returned token.
- **resource_requests_auth.http** – Resource Request Form: signup, login, `my-roles` filtered by `app_key`, and the forgot/reset password pair. The product has no login of its own — it uses the shared `/api/auth`; what belongs to it are the `app_key` and the `equipe` / `mesa` / `gestor` roles. Run `scripts/seed_apps_roles.py` and grant a role first.
- **roles.http** – Role check, assign, revoke. Requires a valid `access_token`: run **Auth: Login** in `auth.http`, copy `tokens.access_token` from the response, and set `@accessToken` at the top of `roles.http`.
- **languages.http** – List, create, get by id/code. Set `@accessToken` after login.
- **organizations.http** – List, create, get by id/slug, add member. Set `@accessToken` after login.
- **phases.http** – Create, list (all or by project), get, update, delete. Also: add, list, and remove dependencies. Set `@accessToken` after login; replace `PHASE_ID`, `PROJECT_ID`, `OTHER_PHASE_ID` with real IDs.
- **projects.http** – List, create, get by id, update location, grant user/org access. Set `@accessToken` after login; replace `LANGUAGE_ID`, `PROJECT_ID`, `ORGANIZATION_ID`, `USER_ID` with real IDs.
- **rag.http** – Upload `.md` document, query, list documents, delete document. Set `@accessToken` after login; replace `DOC_ID` with real id from upload/list response.
- **errors.http** – Examples that trigger 401, 409, etc.

## Base URL

Default is `http://localhost:8000`. Change `@baseUrl` in each file if your server runs elsewhere.

## Auth flow for roles

1. Run **Auth: Login** in `auth.http` (or the login request in `api.http`).
2. Copy `access_token` from the response body.
3. In `roles.http`, set `@accessToken = <paste_token_here>` at the top.
4. Run any request in `roles.http`.
