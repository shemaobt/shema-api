---
status: accepted
date: 2026-09-08
---

# `project_id`, not `team_id`, in the schema, while the product keeps saying team

A **Take** row carried a `team_id` column that held nothing, while the rest of the schema said
project for the same entity. Carrying two words for one thing is how the next person loses an
afternoon, so the column became `project_id`, and every room table that names the owning group
names it that way.

The word did not change in the product. **Team** stays the **Desk**'s word, in the interface
and in the backlog, and the glossary keeps it as the canonical name with project marked as the
schema's spelling of the same entity. The rejected alternative was the mirror image: renaming
the rest of the schema to `team_id` and making the product word the column word. That would
have touched every table and response model on the server to settle a vocabulary question only
the room was asking.

The consequence is that one entity carries two names on purpose, and which one is right
depends on the layer: prose and interface say team, columns and wire fields say project.
