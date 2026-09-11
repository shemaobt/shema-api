## What changes

<!-- The argument, in prose. What used to happen, what holds now. -->

## Does this touch one of Marcia's artifacts?

`DOCTRINE.md` §5.1 — "`prompts/*.md`, the model ladder and its parameters are **Marcia's
artifacts**: any change is a ruling with her word, never an engineering default."

Tick anything this PR moves, and fill the ruling in. A prompt, a model id, a ladder order, an
effort level or a token budget — that is the whole list, and `scripts/sync_doctrine.py --check`
fails the build when one of them leaves `docs/doctrine/MODEL_SEAM` or a vendored artefact leaves
its pin.

- [ ] a prompt under `app/services/internalization_room/prompts/`
- [ ] a model id or a ladder order (`tripod_voice_model`, `tripod_analysis_model`, `tripod_classifier_model`)
- [ ] an effort level, a thinking setting, or a token budget at a `call_agent` site
- [ ] the pin in `docs/doctrine/DOCTRINE_PIN` (a re-sync of a vendored artefact)
- [ ] none of the above

**Her words:**

**Where it is written:**

<!-- Both, or none of the boxes above. A decision with no sentence of hers behind it is the
engineering default §5.1 names, and review stops here: the ruling goes in
docs/doctrine/rulings/ as its own file, and the row that changed points at it by slug. -->

## Verification

<!-- Test count, the gates, and whether the fix was reverted to prove the test fails without it. -->
