---
status: accepted
date: 2026-10-22
---

# The caller's address is the entry Cloud Run's proxy appended

The app mounted uvicorn's `ProxyHeadersMiddleware` with `trusted_hosts="*"`. With `"*"` uvicorn
takes the leftmost `X-Forwarded-For` entry, which is the one the client wrote. Two requests from
one socket with different headers landed in two limit buckets, so every per-IP limit was a toll
a header paid, not a ceiling (ENG-1708).

The rightmost-entry rule is the ticket's. The rest are this change's own decisions:

- **The caller's address is the rightmost `X-Forwarded-For` entry**, the one Cloud Run's front
  end appended. Entries to its left are ignored. No header, or a header with no entry, keeps the
  socket address. A request carrying more than one `X-Forwarded-For` line also keeps the socket
  address: where Google appends is unmeasured, so a client's second line could be the rightmost
  entry.
- **"Came through Cloud Run's proxy" means the process runs on Cloud Run**, read from
  `K_SERVICE`, which Cloud Run sets on every revision. A Cloud Run container has no other
  ingress. Off Cloud Run (local, docker-compose, tests) nothing is mounted: the header is
  ignored and the socket address is the caller.
- **The scheme rewrite stays, under the same condition.** `X-Forwarded-Proto` sets the scheme on
  Cloud Run, because the container speaks plain http and the slash redirect and the Inngest
  sync read `https` from it. With several `X-Forwarded-Proto` lines the last one wins, as in
  uvicorn.
- No limit's number changes.

## Rejected

- `trusted_hosts="*"`: the leftmost entry is the client's own.
- uvicorn's middleware with Cloud Run's peer range: the range is undocumented, and a wrong guess
  drops both the address and the scheme.
- A trusted-hop count of two for our nginx front-ends: their egress address is not ours to name,
  so a client could write the second hop.
- The leftmost entry when it is a public address: it is still client-written.

## Consequences

- The project-health limits (10 new interviews, 60 messages, 60 team-report reads a minute) key
  on project-health-ui's egress address, so they are a ceiling on all its traffic together, per
  egress address and per instance. The Definer's answer: "keying project-health's limits per
  interview/token is a finding for the round's close; Henok decides; no ticket is opened now".
- One anonymous caller can block project-health interviews for everyone: creating one takes no
  auth, its limit is 10 a minute, and everyone behind project-health-ui shares one bucket.
- A caller on IPv6 can still move between addresses of its own /64, so a per-address limit is
  not a per-caller one for them.
- ADR 0064's reason for the demo page's single bucket ("the app trusts `X-Forwarded-For` from
  any host") no longer holds. Its bucket stays (the Definer's answer: out of scope).
- The sound-necklace audit `ip` could now be filled from the trusted address. It is not done
  here.
