// Prose-gloss fallback for codes the aliases table doesn't carry (concept-bank CB_*,
// thread TH_* names). Per docs/build_spec.md §5.4, the prose Meaning Map is the tiebreaker
// for object WORDING only (never for the existence or grounding of content).
//
// A real definition line starts at COLUMN 0 with an em-dash and a gloss:
//   [[CB_0030-Sojourn-Gur]] — לָגוּר / sojourning
//   [[TH_TEN_YEARS_APPROXIMATELY-About-Ten-Years]] — כְּעֶשֶר שָׁנִים / about ten years
// Frontmatter / flags / cross-ref lines instead start with a "- " bullet:
//   "  - [[CB_0051-...]]"  ·  "- [[CB_0051-...]] — active at Proposition 2"  ·  "- Cross-ref: [[...]]"
// We harvest ONLY the column-0, em-dash definition lines (CODE → the english gloss after the
// last " / "). This must never span newlines or accept a bullet line — otherwise a code can
// pick up the NEXT concept's raw [[wikilink]] and that raw code would reach a voiced label.

export function buildProseGlossIndex(meaningMapText: string): Record<string, string> {
  const out: Record<string, string> = {};
  // ^-anchored, single line, em-dash (—) only, slug cannot contain ] or newline.
  const lineRe = /^\[\[([A-Z][A-Z0-9_]*?)-[^\]\n]*\]\][ \t]*—[ \t]*([^\n]+)$/gm;
  let m: RegExpExecArray | null;
  while ((m = lineRe.exec(meaningMapText)) !== null) {
    const code = m[1];
    const rest = m[2].trim();
    const slash = rest.lastIndexOf("/");
    // A gloss may carry a linked name the map's own way, "[[CODE-Slug]] Name" (P12 CB_0010: "the house
    // of [[PL_ISRAEL-Israel]] Israel", 2026-09-27): the link goes, the name the map writes after it
    // stays. A link with no name written after it is still a stray wikilink (rejected below).
    const gloss = (slash >= 0 ? rest.slice(slash + 1) : rest).trim().replace(/\[\[[^\]\n]*\]\][ \t]+(?=\p{L})/gu, "");
    // Reject anything that isn't a clean gloss: a stray wikilink, or an "active at …" flag note.
    if (!gloss || gloss.includes("[[") || /^active at\b/i.test(gloss)) continue;
    if (!out[code]) out[code] = gloss; // first definition wins
  }
  return out;
}
