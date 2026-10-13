// Load a FOR_MODEL artifact. The vendored file is a wiki note (.md) that renders the
// canonical FOR_MODEL JSON inside a ```json fenced block. We parse that block.
// Schema: docs/build_spec.md §5.1. ID-only by design — resolution happens elsewhere.

import { readFileSync } from "node:fs";

export type ForModelBeingEntry = {
  being_id: string;
  role_in_scene: string;
  presence: string;
  referential_form?: string;
};
export type ForModelScene = {
  scene_id: string;
  verse_range: string;
  scene_kind: string;
  scene_communicative_purpose: string;
  beings_in_scene?: { entries?: ForModelBeingEntry[] } | null;
  places_in_scene?: { entries?: { place_id: string }[] | null } | null;
  objects_in_scene?: { entries?: { object_id: string }[] | null } | null;
  times_in_scene?: { entries?: { time_id: string }[] | null } | null;
  significant_absence?: string | null;
};
export type ForModel = {
  sta_id: string;
  tagset_version: string;
  header: {
    bcv: string;
    pericope_title: string;
    source_meaning_map_ref: string;
    [k: string]: unknown;
  };
  pericope_classification?: { register?: string; [k: string]: unknown };
  level_1: {
    arc_elements: string[];
    context_elements: string[];
    tone_elements: string[];
    pace_elements: string[];
    communicative_function_elements: string[];
  };
  level_2_scenes: ForModelScene[];
  level_3_propositions?: unknown[];
};

// Extract the canonical artifact JSON. Scans EVERY ```json block and returns the first that
// satisfies `isShape` (so an illustrative/example block can't be parsed by accident). When no
// validator is given, returns the first block.
export function extractFencedJson(
  text: string,
  path: string,
  isShape?: (v: unknown) => boolean
): unknown {
  const blocks = [...text.matchAll(/```json\s*([\s\S]*?)```/g)];
  if (blocks.length === 0) throw new Error(`no \`\`\`json block found in ${path}`);
  const parsed: unknown[] = [];
  for (const b of blocks) {
    try {
      parsed.push(JSON.parse(b[1]));
    } catch (e) {
      // tolerate a non-canonical block that doesn't parse, as long as a later one does
      if (!isShape && blocks.length === 1) throw new Error(`invalid JSON in ${path}: ${(e as Error).message}`);
    }
  }
  if (!isShape) {
    if (parsed.length === 0) throw new Error(`no parseable \`\`\`json block in ${path}`);
    return parsed[0];
  }
  const match = parsed.find((v) => isShape(v));
  if (!match) throw new Error(`no \`\`\`json block in ${path} matches the expected artifact shape`);
  return match;
}

export function loadForModel(path: string): ForModel {
  const fm = extractFencedJson(
    readFileSync(path, "utf8"),
    path,
    (v): boolean => !!v && typeof v === "object" && "level_1" in v && "level_2_scenes" in v
  ) as ForModel;
  if (!fm.level_2_scenes || !fm.level_1) throw new Error(`${path} missing level_1/level_2_scenes`);
  return fm;
}
