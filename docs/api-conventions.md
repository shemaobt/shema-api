# API conventions

One router per domain area, registered in the application module. Protected routes take the
shared dependencies that live with the authentication middleware rather than re-deriving the
current user.

A router parses and validates input, calls a service, and maps expected business exceptions
onto HTTP responses. That is the whole of what belongs in it — no query, no orchestration, no
table model construction. The rule and the reason are
[ADR 0009](adr/0009-routers-never-touch-the-database.md).

Services raise the business exceptions defined in the shared exceptions module — not found,
conflict, role — and never import the HTTP exception type. A router maps one onto a status
code, or the global handlers do it.

For infrastructure and genuinely unexpected failures, leave the framework's own behaviour
alone. Wrapping every exception costs the traceback and buys a worse message.

Request and response shapes are Pydantic models, kept apart from the table models. Prefer an
explicit typed model over a bare dictionary wherever the shape is known.
