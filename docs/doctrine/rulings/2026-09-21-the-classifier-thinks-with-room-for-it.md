# The classifier thinks, with room for it

pin: 533b6e3f338f1a0077c025a8de0edd89f5a4f4cd
governs: the coverage classifier's own call in classify_coverage.py — thinking and its output ceiling
word: "Classifier: thinking on, and raise the ceiling with it. … In my stack the classifier runs with adaptive thinking and an output ceiling of 6000 tokens. At 1500 we had exactly your empty replies, on 9 September, and 6000 cured them. It is off the voice path, so the team never waits for it."
written: ENG-974, her comment B7 of 2026-09-21

The row was `unruled` at `thinks=False`, `max_output_tokens=4096`: ours, chosen to keep the
9 September empty replies from recurring by turning thinking off rather than by giving it
room. Her word above is the opposite fix — thinking stays on everywhere, per §6's "I want all
models thinking", and the ceiling moves to what her own stack already measured cured, not
merely enlarged, the same empty-reply failure. `MODEL_SEAM` now credits the row to this ruling
instead of freezing it at an engineering default.

This supersedes a sentence in `docs/doctrine/rulings/2026-09-03-the-model-seam-is-hers.md:10-11`
— "§2.4 allows the classifier off the voice path, which is the one row in `MODEL_SEAM` that
carries `thinks=False`" — which described that row. The row this ruling governs now carries
`thinks=True`; that sentence is not amended in place, since her word there stands for what it
did rule, only the row underneath it moved.
