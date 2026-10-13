// Assemble a resolved, normalized ParsedMap from the FOR_MODEL (structure/IDs) + the
// Compilation Log (audit) + the resolver (names). See docs/build_spec.md §5.2.

import type { ParsedMap, Scene, BeingMention, ResolvedRef, AuditEntry } from "./types.ts";
import type { ForModel, ForModelScene } from "./forModel.ts";
import type { Resolver } from "./aliases.ts";
import { PASSAGE_LABEL } from "./referentialForms.ts";

function pericopeIdFrom(ref: string): string {
  // "P01-Ruth-1-1-5" → "P01"
  const m = ref.match(/^([PJ]\d+)/);
  return m ? m[1] : ref;
}

function resolveBeings(scene: ForModelScene, r: Resolver): BeingMention[] {
  const entries = scene.beings_in_scene?.entries ?? [];
  return entries.map((b) => ({
    id: b.being_id,
    role: b.role_in_scene,
    presence: b.presence,
    referentialForm: b.referential_form,
    ...r.resolve(b.being_id, b.referential_form, b.role_in_scene),
  }));
}

// A passage's own word for the code (PASSAGE_LABEL) replaces the registry name as the displayed label.
function resolveRefs(ids: string[], r: Resolver, pericopeId: string): ResolvedRef[] {
  return ids.map((id) => {
    const label = PASSAGE_LABEL[pericopeId]?.[id];
    return label ? { id, ...r.resolve(id), spokenForm: label, displayName: label } : { id, ...r.resolve(id) };
  });
}

export function buildParsedMap(fm: ForModel, audit: AuditEntry[], r: Resolver): ParsedMap {
  const pericopeId = pericopeIdFrom(fm.header.source_meaning_map_ref);
  const scenes: Scene[] = fm.level_2_scenes.map((s) => ({
    id: s.scene_id,
    verseRange: s.verse_range,
    kind: s.scene_kind,
    communicativePurpose: s.scene_communicative_purpose,
    beings: resolveBeings(s, r),
    places: resolveRefs((s.places_in_scene?.entries ?? []).map((e) => e.place_id), r, pericopeId),
    objects: resolveRefs((s.objects_in_scene?.entries ?? []).map((e) => e.object_id), r, pericopeId),
    times: resolveRefs((s.times_in_scene?.entries ?? []).map((e) => e.time_id), r, pericopeId),
    significantAbsence: s.significant_absence ?? null,
  }));

  return {
    pericopeId,
    reference: fm.header.bcv,
    title: fm.header.pericope_title,
    register: (fm.pericope_classification?.register as string) ?? "",
    level1: {
      arc: fm.level_1.arc_elements,
      context: fm.level_1.context_elements,
      tone: fm.level_1.tone_elements,
      pace: fm.level_1.pace_elements,
      communicativeFunction: fm.level_1.communicative_function_elements,
    },
    scenes,
    preservationRules: audit.filter((a) => a.doNotDecide), // Validator hard constraints
    audit,
  };
}
