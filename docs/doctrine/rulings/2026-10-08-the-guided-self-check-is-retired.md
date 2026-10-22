# The guided self-check is retired

pin: 18fa7c41f037e9f8728986400f5fcb4b3c243c4b
governs: `draft_check_system_prompt.md`, the ninth of her prompts, her instructions for the guided self-check «Vamos conferir juntos»: it leaves the room's prompts and the freeze pin, and her prompts are eight in use plus one retired
word: "Production scope. Yours, with two lines that stay mine: nothing the team or a listener recorded is deleted without my word, and the listeners' consent (ch. 18). Backup, and how long things are kept, are yours."
written: 2026-10-01 — Marcia's answers of 1 October 2026 (Linear document «Marcia's answers of 1 October 2026 (the bar, acceptance, changes)»), under «Production scope»

The decision is the production team's, João's on 8 October 2026: retire the guided self-check
(ENG-1246). No screen offers it, and the server neither keeps nor uses her self-check
instructions.

It falls inside what she handed over. The self-check was a facilitator-only path that was never
shipped here, so retiring it deletes nothing the team or a listener recorded and touches no
listener's consent, the two lines she kept. `RETIRED_PROMPTS` in `scripts/sync_doctrine.py` names
this ruling, and `--check` fails if the file or its pin row returns, or if the ruling stops
carrying her sentence.
