# Authentication — the shared `/api/auth`

Every app this server serves signs its people in through the same routes and the same
`users` table. What belongs to each app is its `app_key` and its roles; what is shared is the
session. Routes live in `app/api/auth.py`, the logic in `app/services/auth/`.

## The session

Login and signup answer a pair: an **access token** (a JWT of type `access`, good for
`access_token_expire_minutes`, 30) and a **refresh token** (a JWT of type `refresh`, seven
days). Only the refresh token has a row: its SHA-256 in `refresh_tokens`, revoked by
`/logout` one at a time and by a password reset all at once. The access token has no row and
cannot be taken back; it simply runs out.

Whether a refresh token is still good is decided in one place,
`read_live_refresh_token` — signed, of type `refresh`, a row nobody revoked, a clock that has
not run out. `/refresh` reads it to issue a new access token, and the handoff reads it to
decide whether a session may be carried somewhere else.

Two things are not done yet and belong to INT-01, not to any route here: the refresh token
is not rotated on use, and it is not an httpOnly cookie — each front keeps its own pair.

## Access to an app

`require_app_access(app_key)` (`app/core/access_control.py`) admits a platform admin, and
anybody else holding a live role in the app; `require_role` asks for one role. Both read the
account and its roles through thirty-second caches (`app/core/auth_cache.py`), the right
trade for a question asked on every request.

## The handoff — one session, carried into another app (BE-21)

A person signed in to one app opens another without typing a password again: the first app
asks for a **handoff code**, opens the second with the code in the URL, and the second trades
it for a session of the same person. It is what makes *"o formulário não tem login"*
(OBT-522) true for the PME and the resource-request form, and it serves any app of this
server.

```
POST /api/auth/handoff           {app_key, refresh_token, context?} -> {code, expires_at}   201
POST /api/auth/handoff/exchange  {code}                             -> {user, tokens, context}
```

**Why a code and not the JWT in the URL.** A URL leaks — into history, proxy logs and
`Referer` — and an access token there is thirty minutes of somebody's session, a refresh
token seven days. A code is 256 bits (`tokens.mint()`), lives sixty seconds
(`auth_handoff_code_expire_seconds`), opens once, and only its digest is stored. The asking
app puts it in the URL **fragment** (`…/entrar#code=…`), which the browser sends to no server
and to no `Referer`; the receiving app reads it, exchanges it and clears the URL.

**Asking for one** takes a signed-in session and more than a signature:

- The body carries the session's own **refresh token**, which has to be live and the caller's.
  The bearer token alone cannot say whether its session still exists — it is stateless for
  thirty minutes after a logout or a password reset — and the exchange pays out a new
  seven-day refresh token. A handoff minted off a bearer alone would turn any access token
  that leaked into a session with no end, one that survives the password reset that revoked
  every other.
- The account is re-read, not taken from the cache, and must be active.
- The app must exist (else 422 `UNKNOWN_REFERENCE`), and the account must hold a live role in
  it or be a platform admin (else 403) — `require_app_access`'s rule, read from the database
  because minting a credential is a write that matters, the distinction `holds_capability`
  draws (`docs/resource_requests.md` §5.5).
- `context` is a JSON object the server never reads — the PME sends `{"projectId": …}` so the
  form opens the right instance — handed back exactly as it came. At most 1024 bytes of
  compact UTF-8 JSON, and no `NaN` or `Infinity`; either refusal is 422
  `UNPROCESSABLE_VALUE`, raised by the service because a refusal from the request model echoes
  its input and the echo of a `NaN` cannot be serialised.

Nothing is written until all of that has passed.

**Exchanging it** is public: the code is the credential. The code is spent by a guarded
`UPDATE … WHERE used_at IS NULL`, so two exchanges racing for one code cannot both win, and
the spend commits together with the refresh row `issue_tokens` writes. The answer is login's
— `user` and `tokens` — plus `context`. An inactive account is refused with 403 and its code
is left unspent. The grant is not checked again: the session issued is not scoped to an app,
and every route of the destination app checks its own grant on every request.

The refusals are 401, each with its own `code`, so the receiving app can say what happened
and send the person back where they came from:

| `code` | When |
|---|---|
| `HANDOFF_CODE_UNKNOWN` | No code with that digest was ever issued |
| `HANDOFF_CODE_EXPIRED` | Its sixty seconds are over |
| `HANDOFF_CODE_USED` | It was already exchanged |

The states are read by `tokens.status`, in the module's order (`docs/shema.md` §6.7): a code
already used and presented again after its minute reads as **expired**, not used. A
`HANDOFF_CODE_USED` inside the minute is also the one sign that somebody else may have been
first, and every refusal is logged with its reason and the row's id — never the code.

**The limit.** The exchange takes `auth_handoff_exchange_limit_per_minute` (10) attempts per
address. slowapi's bucket is the address together with the URL path, so the code travels in
the body and must stay there — in the path it would become part of every bucket key. The
address is what `ProxyHeadersMiddleware(trusted_hosts="*")` resolves, which is the first
`X-Forwarded-For` entry and one a caller can change, so the limit is a toll on guessing and
not a ceiling. The code's 256 bits are what guard it.

**The table.** `auth_handoff_codes` — `user_id`, `app_id`, `code_hash`, `context`,
`expires_at`, `used_at`, `created_ip`, `created_at` — is a table of its own, as every token
purpose is. It has no `revoked_at`, because nothing takes back a code that lives a minute;
`tokens.status` reads it through a view that says *never revoked*. `created_ip` is the address
the asking request presented, parsed as an IP or stored as NULL: the same proxy trust makes it
a lead beside `user_id`, never evidence on its own. Both foreign keys cascade, and rows stay
after the spend as the trail of who went from where to which app; nothing purges them yet.

### What the handoff does not close

- **A stolen refresh token that is still live** can be carried from handoff to handoff, each
  exchange paying a fresh seven days, until a logout or a password reset revokes it — where
  before it ended with its own seven days. Rotating the refresh token, or a carried session
  that cannot outlive the one it came from, is INT-01's.
- **The receiving browser is not bound to the asking one.** A code minted by one account and
  opened in somebody else's browser signs that browser in as the minter. The answer carries
  `user`, so the receiving app can say who is signing in; binding the code to the browser that
  receives it would need that app to start the flow.
