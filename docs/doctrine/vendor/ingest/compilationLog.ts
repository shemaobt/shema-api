// Load a Compilation Log artifact and surface its high_risk_register_audit — the
// Validator's preservation/prohibition list and the source of significant-absence teaching.
// See docs/build_spec.md §2.2. do_not_decide === true ⇒ HARD constraint.

import { readFileSync } from "node:fs";
import type { AuditEntry } from "./types.ts";
import { extractFencedJson } from "./forModel.ts";

type RawAudit = {
  id: string;
  kind: string;
  applies_to?: string;
  note?: string;
  do_not_decide?: boolean;
  required_in_audit?: boolean;
  source_in_meaning_map?: string;
  carries_forward_to?: string;
};

export function loadCompilationLog(path: string): { audit: AuditEntry[] } {
  const log = extractFencedJson(
    readFileSync(path, "utf8"),
    path,
    (v): boolean => !!v && typeof v === "object" && "high_risk_register_audit" in v
  ) as { high_risk_register_audit?: RawAudit[] };
  const raw = log.high_risk_register_audit ?? [];
  const audit: AuditEntry[] = raw.map((a) => ({
    id: a.id,
    kind: a.kind,
    appliesTo: a.applies_to ?? "",
    note: a.note ?? "",
    doNotDecide: a.do_not_decide === true,
    requiredInAudit: a.required_in_audit,
    sourceInMeaningMap: a.source_in_meaning_map,
    carriesForwardTo: a.carries_forward_to,
  }));
  return { audit };
}
