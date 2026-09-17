---
status: accepted
date: 2026-09-08
---

# Routers never touch the database, and services never raise HTTP

The API layer is an access layer for HTTP and nothing else. A router parses and validates
input, calls a service, and maps expected business exceptions onto HTTP responses. It runs no
query, writes through no session, constructs no table model, and imports no query construct
beyond the injected session it hands on.

All data access lives in the service layer, and so does every business rule and all
orchestration. A service that has to refuse raises a business exception from the shared
exceptions module — not found, conflict, role — and never imports the HTTP exception type. The
router maps it, or the global handlers do.

The rejected alternative is the convenient one: a router that runs a small query because the
service function for it does not exist yet. It is rejected because this boundary is only worth
anything while it holds everywhere. One router with a query in it turns the layer into a
suggestion, and the next reader has to open every router to find out where the rules live.
