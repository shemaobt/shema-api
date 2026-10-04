# The Portuguese B, C and E lines enter her file

pin: 533b6e3f338f1a0077c025a8de0edd89f5a4f4cd
governs: the authored fail-safe utterances, which now carry B-pt, C-pt and E-pt beside A-pt, D-pt and F-pt — a third divergence from the vendored copy, alongside G (retired, 2026-09-16) and X (2026-09-15)
word: "B and C: already confirmed ... in exactly this text, as reserve, with 'o facilitador de vocês' ... You can enter them." and "E: yes, the whole sentence, as you wrote it: 'Vamos fazer uma pausa curta aqui ...'" "B, C and E remain reserve lines."
written: ENG-833, item A1, 2026-09-21

The Portuguese for B, C and E was written 2026-08-10, sent to her 2026-09-17, and until this
ruling lived only in `_fail_safe_pt_supplement.md` — approved off-repo, never in her structure.
`_fail_safe_pt_supplement_provenance.md` carries that history in full.

Her word above moves the three blocks into `fail_safe_utterances.md` as B-pt, C-pt and E-pt,
byte-identical to what the supplement carried. B and C stay reserve: nothing in code may route
to `FailSafe.OUTSIDE_MAP` or `FailSafe.HANDOFF` (`tests/test_ir_b_and_c_have_no_caller.py`), her
word above changes their text's home, not their reachability. E is unchanged in meaning — it was
already the authored file's own English E, mirrored — and now has its Portuguese beside it the
same way.
