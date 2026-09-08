---
status: accepted
date: 2026-09-08
---

# A **Halt** travels beside the status, carries a kind, and an older one reads as blocking

A room that stopped for a person has not ended, so the reason it stopped is not a value of the
state it is in. **Halt kind** (`halt_kind`) is a column of its own holding blocking or warning,
read back through an enum so that a caller cannot invent a third kind by spelling one.

Both stops used to be written as **Needs a person**, and no reader could tell them apart. A
hard stop means the room cannot go on: nothing further lands until a person comes. A retell
budget running out refuses nothing — the team may go on telling, and the room is asking for a
witness. They are different walks for the facilitator, and the **Desk** had one word for both.

The kind is a short string column rather than a Postgres enum, for the reason `bridge_mode` is
one: a database type is a second place the vocabulary lives, and a migration on both sides
every time it grows a value.

A row halted before the distinction existed carries no kind and is answered blocking. That is
the conservative reading: treating an unknown halt as one that stops the room sends somebody
to a team that did not need them, while the other way round leaves a stopped room waiting.

What has not moved yet is **Needs a person** itself. On `main` it is still a value of the
**Session** status enum, so today the kind of a halt travels beside the status while the fact
of it still travels inside. Taking it out of the status is ENG-605, which is not merged.
