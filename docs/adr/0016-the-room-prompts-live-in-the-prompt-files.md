---
status: accepted
date: 2026-09-11
---

# The room's prompts live in the repository's prompt files, not in the database

The room once read a prompt from a stored row when one existed and fell back to the committed
markdown file beside the service. No writer for that row was ever built, so the file was the
only path ever exercised while nobody could say which prompt production was running. On
2026-09-02 the fallback became the rule: `get_prompt_text` reads the file, and migration
`20260902_room09` dropped the table, its enum and the seeder nothing called.

Decided, and recorded here because the migration's docstring was the only place it lived: a
prompt is a file in the repository, reviewed in a pull request like code, and the **Analyst**
and **Speaker** prompts are Marcia's artifacts copied in her words (ADR 0012). There is no
runtime editor and none is wanted: a prompt that can be changed without a diff is a prompt
nobody can audit.

Consequence: the file is read once per process and cached, so a prompt change reaches
production only with the deploy that carries it, never by editing a file on a running
instance.
