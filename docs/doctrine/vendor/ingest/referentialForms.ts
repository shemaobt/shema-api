// Form-aware resolution: map a FOR_MODEL `referential_form` TOKEN to the spoken form.
// See docs/build_spec.md §2.1 ("Form-aware resolution") and CLAUDE.md Hard Rule #4.
//
// Two notations describe the same phenomenon: the FOR_MODEL marks forms as tokens
// (STRIPPED_TO_HA_ISHAH), the aliases table lists them as human strings ("the woman").
// This table bridges them. Priority per mention: referential_form token (mapped) → else
// the aliases `english` name.

export const FORM_TOKEN_TO_SPOKEN: Record<string, string> = {
  // Meaning-bearing strip: Naomi de-named to "the woman" at 1:5 (Compilation Log R4).
  // This is the single sharpest form rule — "the woman", never "Naomi", at S4.
  STRIPPED_TO_HA_ISHAH: "the woman",
  SHE_PRONOMINAL: "she",

  // Introduce-before-naming at 1:1 (the family is named in 1:2). The narrator opens with
  // an unnamed family, then names them within the scene — so these are the spoken form for
  // the early mention, but the being's identity is still the plain name (see isIdentityStrip).
  UNNAMED_MAN_FROM_BETHLEHEM: "a man of Bethlehem",
  UNNAMED_WIFE_OF_HEAD: "his wife",
  UNNAMED_FIRST_SON: "his first son",
  UNNAMED_SECOND_SON: "his second son",

  // Ruth 4:9–22 (P12–P14, SC-0088): the map's own words for the mention, where the plain humanizer
  // would say something the text does not ("ruth the moabitess", "redeemer goel", "salmah and salmon"
  // read as two people). Each string is the map's heading gloss or referential-form line for that
  // scene; none is a new reading. RUTH_THE_MOABITESS is also the token of P07 S3 (2:21), whose map
  // says "Ruth the Moabite" too.
  HUSBAND_OF_RUTH: "Mahlon", // P12 S1 (4:9–10): named by Boaz; Ruth is "the wife of Mahlon"
  RUTH_THE_MOABITESS: "Ruth the Moabite", // P12 S1 (4:10) "Ruth the Moabite, the wife of Mahlon"; P07 S3 (2:21)
  WOMAN_COMING_INTO_HOUSE: "the woman coming into your house", // P12 S2 (4:11)
  DAUGHTER_IN_LAW_WHO_LOVES_YOU: "your daughter-in-law who loves you", // P13 S2 (4:15)
  REDEEMER_GOEL: "a redeemer", // P13 S2 (4:14), the child the women speak of — the B? of that scene
  SALMAH_AND_SALMON: "Salmah / Salmon (one name, spelled two ways)", // P14 S1 (4:20–21): one ancestor

  // Ruth 3:1–5 and 3:14–18 (P08, P10, SC-0089): the plain humanizer carried a Hebrew transliteration
  // into the form word ("our kinsman moda", "ha ish the man", "her mother in law chamot"). Each string
  // is the map's own referential-form line for that scene; none is a new reading. HA_ISH_THE_MAN is
  // also the token of P09 S2 (3:8 "the man"), and MY_DAUGHTER of P09 S3; both maps say so too.
  OUR_KINSMAN_MODA: "our kinsman", // P08 S1 (3:2) "Boaz our kinsman" (מֹדַעְתָּנוּ, a family word)
  HA_ISHAH_THE_WOMAN: "the woman", // P10 S1 (3:14) "the woman" in Boaz's words
  HA_ISH_THE_MAN: "the man", // P10 S2 (3:16, 3:18); P09 S2 (3:8)
  HER_MOTHER_IN_LAW_CHAMOT: "her mother-in-law", // P10 S2 (3:16)
  MY_DAUGHTER: "my daughter", // P08 S1 (3:1); P09 S3; P10 S2 (3:16, 3:18)
  NAOMI_HER_MOTHER_IN_LAW: "Naomi her mother-in-law", // P08 S1 (3:1) "Naomi her mother-in-law" (נָעֳמִי חֲמוֹתָהּ)
};

// A referential form OVERRIDES the element's displayed identity only when it is a
// meaning-bearing *strip* of an already-established name (Naomi → "the woman"), not when it
// is a transient introduce-before-naming form (which resolves to the plain name within the
// scene). This is exactly what makes Appendix A show plain names at S1 but "the woman" at S4.
export function isIdentityStrip(token: string | undefined): boolean {
  return typeof token === "string" && token.startsWith("STRIPPED_TO_");
}

// Plain-meaning fallback for an unmapped token (spec §2.1: "fall back to the token's plain
// meaning"). Lowercased, underscores → spaces. Logged by the resolver so misses are visible.
export function humanizeToken(token: string): string {
  return token.toLowerCase().replace(/_/g, " ").trim();
}

// A withheld referent — the being code `B?` (the schema's `^B(\d+|\?)$`): the map declines to bind the
// mention to a registered being (P06's "her husband", P11's "the dead", P13's son). It gets a grounded
// label instead of the unresolved placeholder (Marcia's ruling 2026-09-27, SC-0087): from its
// referential_form when present — the form table's words when the token is in it (REDEEMER_GOEL →
// "a redeemer", SC-0088), else lower-case, underscores to spaces, a trailing UNNAMED dropped and
// " (unnamed here)" added (THE_DEAD_UNNAMED → "the dead (unnamed here)"); with no form, the word the
// text uses for its role when WITHHELD_ROLE_LABEL has one (P13 S1, 4:13 "she bore a son" → "a son"),
// else WITHHELD_BEING_LABEL.
export const WITHHELD_BEING = "B?";
export const WITHHELD_BEING_LABEL = "someone the text leaves unnamed here";
// Only roles whose word is the text's own for every B? that carries it: SON = P13 S1 alone (the map's
// uncoded heading "The child — בֵּן / "a son""). P06 S2 (HUSBAND) keeps the generic label.
export const WITHHELD_ROLE_LABEL: Record<string, string> = { SON: "a son" };
export function withheldBeingLabel(token: string | undefined, role?: string): string {
  if (!token) return (role && WITHHELD_ROLE_LABEL[role]) || WITHHELD_BEING_LABEL;
  if (FORM_TOKEN_TO_SPOKEN[token]) return FORM_TOKEN_TO_SPOKEN[token];
  const words = humanizeToken(token).split(/\s+/).filter(Boolean);
  if (words[words.length - 1] === "unnamed") {
    words.pop();
    return words.length ? `${words.join(" ")} (unnamed here)` : WITHHELD_BEING_LABEL;
  }
  return words.length ? words.join(" ") : WITHHELD_BEING_LABEL;
}

// A passage's own word for a registered code, where one code covers two different words of the text and
// the registry's name is the other passage's word (Marcia's standard of 2026-09-28, items 1 and 10: the
// coverage list names what the text has, as the text names it). Keyed by passage, then code; Title Case
// like the registry. Only the element's label moves: the ledger line, the bead, the label the classifier
// reads and the label's session-language keys (src/coverage/sessionForms.ts). The code, the registry
// entry and the canon stay as they are. Read by buildParsedMap for places, objects and times
// (src/ingest/parseMap.ts).
//   P10 O13: 3:15 is mitpachat, "the cloak" (the P10 map's heading: הַמִּטְפַּחַת / "the cloak"); the
//   registry's "Your Garments" is the simlah of 3:3, which P08 keeps.
export const PASSAGE_LABEL: Record<string, Record<string, string>> = {
  P10: { O13: "The Cloak" },
};

export function spokenFormForToken(token: string): { spoken: string; mapped: boolean } {
  const hit = FORM_TOKEN_TO_SPOKEN[token];
  return hit ? { spoken: hit, mapped: true } : { spoken: humanizeToken(token), mapped: false };
}
