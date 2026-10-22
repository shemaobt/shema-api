// Flatten a ParsedMap into the independently-trackable coverage-element list.
// See docs/build_spec.md §5.3. Status starts at not_encountered; only `engaged` counts.
//
// De-duplication rule (§5.3): a significant-absence element and a preservation rule about
// the SAME silence are ONE element. So a STRUCTURAL_ABSENCE_* audit entry is folded into the
// matching scene-absence element (carrying its hard-constraint flag) rather than becoming a
// separate preserved_element. Other do_not_decide rules (a required keep-image, a withheld
// pairing) ARE their own preserved_element coverage items.

import type { ParsedMap, CoverageElement, AuditEntry } from "./types.ts";

const STRUCTURAL_ABSENCE = /^STRUCTURAL_ABSENCE_/;

// Which scene-absences a structural-absence audit entry pertains to, by the silence it names.
// Enrichment only (teaching + hard-constraint tag); the absence element set is fixed at the
// 4 scene absences, so an imperfect match can never drop or invent a coverage element.
function absenceMatchesAudit(absenceText: string, audit: AuditEntry): boolean {
  const t = absenceText.toLowerCase();
  if (/DIVINE_AGENCY/.test(audit.kind)) return /\bgod\b|yhwh|cause|act of god|sent/.test(t);
  if (/GRIEF/.test(audit.kind)) return /grief|mourn|funeral/.test(t);
  // "no children born / names no child" — anchored to actual childlessness wording, not the
  // bare word "line" (which also appears in S4's "no one left to carry on the line").
  if (/OFFSPRING/.test(audit.kind)) return /child|children|offspring|\bheir\b/.test(t);
  return false;
}

export function buildCoverageElements(map: ParsedMap): CoverageElement[] {
  const out: CoverageElement[] = [];
  const add = (e: Omit<CoverageElement, "status">) => out.push({ ...e, status: "not_encountered" });

  // --- Level 1 (four abstract axes; narrated from prose later) -------------------
  const l1: Array<["arc" | "context" | "tone" | "function", string[]]> = [
    ["arc", map.level1.arc],
    ["context", map.level1.context],
    ["tone", map.level1.tone],
    ["function", map.level1.communicativeFunction],
  ];
  for (const [kind, tokens] of l1) {
    add({ id: `L1:${kind}`, kind, label: `Level-1 ${kind}`, detail: tokens.join(", ") });
  }

  // --- per scene: the scene event, then beings/places/objects/times -------------
  const structural = map.audit.filter((a) => STRUCTURAL_ABSENCE.test(a.kind));
  for (const s of map.scenes) {
    add({
      id: `scene:${s.id}`,
      kind: "scene",
      sceneId: s.id,
      label: `${s.id} (${s.verseRange}) — ${s.communicativePurpose}`,
      detail: s.kind,
    });

    for (const b of s.beings) {
      add({
        id: `being:${s.id}:${b.id}`,
        kind: "being",
        sceneId: s.id,
        code: b.id,
        label: b.displayName, // honors "the woman" at S4; plain names elsewhere; never a code
        role: b.role || undefined,
        unresolved: !b.resolved,
        detail: `${b.role} · ${b.presence}` + (b.referentialForm ? ` · form=${b.referentialForm} (say: "${b.spokenForm}")` : ""),
      });
    }
    for (const p of s.places) add({ id: `place:${s.id}:${p.id}`, kind: "place", sceneId: s.id, code: p.id, label: p.displayName, unresolved: !p.resolved });
    for (const o of s.objects) add({ id: `object:${s.id}:${o.id}`, kind: "object", sceneId: s.id, code: o.id, label: o.displayName, unresolved: !o.resolved, detail: o.source === "prose-gloss" ? "(wording from prose Meaning Map)" : undefined });
    for (const t of s.times) add({ id: `time:${s.id}:${t.id}`, kind: "time", sceneId: s.id, code: t.id, label: t.displayName, unresolved: !t.resolved });

    // --- significant absence (high priority) + folded structural-absence audit ---
    if (s.significantAbsence) {
      const related = structural.filter((a) => absenceMatchesAudit(s.significantAbsence as string, a));
      add({
        id: `absence:${s.id}`,
        kind: "significant_absence",
        sceneId: s.id,
        label: `Significant absence @ ${s.id}`,
        detail: s.significantAbsence,
        hardConstraint: related.some((a) => a.doNotDecide),
        relatedAudit: related.map((a) => a.id),
      });
    }
  }

  // --- preserved_element: do_not_decide rules NOT already folded into an absence -
  const foldedAuditIds = new Set(out.flatMap((e) => e.relatedAudit ?? []));
  for (const a of map.preservationRules) {
    if (STRUCTURAL_ABSENCE.test(a.kind) && foldedAuditIds.has(a.id)) continue; // de-duped into the absence
    add({
      id: `preserved:${a.id}`,
      kind: "preserved_element",
      label: `${a.id} — ${a.kind}`,
      detail: a.note,
      code: a.id,
      hardConstraint: true,
    });
  }

  return out;
}
