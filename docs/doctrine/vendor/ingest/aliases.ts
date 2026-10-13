// ID → name resolution. Load <book>.aliases.json once (whole book), resolve by code,
// form-aware. See docs/build_spec.md §2.1 and §5.4.

import { readFileSync } from "node:fs";
import type { AliasesFile, AliasEntity, Resolution } from "./types.ts";
import { UNRESOLVED_LABEL } from "./types.ts";
import { isIdentityStrip, spokenFormForToken, WITHHELD_BEING, WITHHELD_BEING_LABEL, withheldBeingLabel } from "./referentialForms.ts";

export function loadAliases(path: string): AliasesFile {
  const data = JSON.parse(readFileSync(path, "utf8")) as AliasesFile;
  if (!data.entities || typeof data.entities !== "object") {
    throw new Error(`aliases file ${path} has no 'entities' map`);
  }
  return data;
}

// Retired/reserved entries carry bracketed admin text and/or a marker on the entity KEY
// (e.g. I5_RETIRED, the reserved range key O23-O25); never voice them and never let them
// become coverage elements (spec §5.4). The marker lives on the code/key, not on `kind`.
export function isRetiredOrReserved(entity: AliasEntity | undefined, code = ""): boolean {
  if (!entity) return false;
  const e = entity.english ?? "";
  return (
    /\[(retired|reserved)/i.test(e) ||
    /_RETIRED$/i.test(code) || // I5_RETIRED
    /^[A-Z]+\d+-[A-Z]*\d+$/.test(code) // reserved range key, e.g. O23-O25
  );
}

export type Resolver = {
  resolve: (code: string, referentialForm?: string, role?: string) => Resolution; // role: only a B?'s label reads it
  appearsIn: (code: string, pericopeId: string) => boolean;
  misses: string[]; // codes that fell back to prose or failed — surfaced, never silent
};

export function makeResolver(
  aliases: AliasesFile,
  proseGloss: Record<string, string> = {}
): Resolver {
  const misses: string[] = [];

  function resolve(code: string, referentialForm?: string, role?: string): Resolution {
    // A withheld referent (B?) is never in the aliases table, by design: its grounded label comes
    // from its own referential form, or with none from its role's word in the text
    // (src/ingest/referentialForms.ts, Marcia's ruling 2026-09-27; SC-0088).
    if (code === WITHHELD_BEING) {
      const label = withheldBeingLabel(referentialForm, role);
      const via = referentialForm ? ` ${referentialForm}` : role && label !== WITHHELD_BEING_LABEL ? ` role ${role}` : "";
      misses.push(`${code} (withheld referent${via}; grounded label "${label}")`);
      return { code, canonicalName: label, referentialForm, spokenForm: label, displayName: label, source: "withheld", resolved: true };
    }
    const entity = aliases.entities[code];
    let canonicalName: string | null = null;
    let source: Resolution["source"] = "unresolved";

    if (entity && !isRetiredOrReserved(entity, code)) {
      canonicalName = entity.english;
      source = "aliases";
    } else if (proseGloss[code]) {
      canonicalName = proseGloss[code];
      source = "prose-gloss";
      misses.push(`${code} (not in aliases; used prose gloss "${proseGloss[code]}")`);
    } else {
      misses.push(`${code} (UNRESOLVED — not in aliases or prose)`);
    }
    const resolved = canonicalName !== null;

    // Form-aware spoken form. An unmapped token falls back to its plain meaning, never the code.
    let spokenForm: string;
    if (referentialForm) {
      const { spoken, mapped } = spokenFormForToken(referentialForm);
      spokenForm = spoken;
      if (!mapped) misses.push(`${code} form token ${referentialForm} (unmapped; humanized)`);
    } else {
      spokenForm = canonicalName ?? UNRESOLVED_LABEL;
    }

    // The displayed identity honors a meaning-bearing strip (Naomi → "the woman"); a transient
    // introduce-before-naming form keeps the plain name. NEVER emit the raw code as a label.
    const displayName = isIdentityStrip(referentialForm)
      ? spokenForm
      : canonicalName ?? UNRESOLVED_LABEL;

    return { code, canonicalName, referentialForm, spokenForm, displayName, source, resolved };
  }

  function appearsIn(code: string, pericopeId: string): boolean {
    const e = aliases.entities[code];
    return Boolean(e?.appears_in?.includes(pericopeId));
  }

  return { resolve, appearsIn, misses };
}
