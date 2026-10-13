// Core types for M1 — map ingestion, ID resolution, and the coverage spine.
// See docs/build_spec.md §5 (data model) and §2 (the three artifacts).

export type Presence = "PRESENT" | "REFERENCED" | "PRESENT_BECOMES_DECEASED" | string;

// --- aliases table (_spec/registry/<book>.aliases.json, schema tripod-entity-aliases)
export type AliasEntity = {
  kind: string; // PERSON | PLACE | THING | TIME | INSTITUTION | ...
  english: string;
  hebrew?: string | null;
  hebrew_cons?: string | null;
  referential_forms?: string[];
  appears_in?: string[]; // pericope ids, e.g. ["P01","P02"]
  gender?: string | null;
};
export type AliasesFile = {
  book?: string;
  schema?: string;
  schema_version?: string;
  entities: Record<string, AliasEntity>;
};

// --- the result of resolving one ID (form-aware). The Guide NEVER voices a code.
export type Resolution = {
  code: string;
  canonicalName: string | null; // plain `english` (or prose gloss); the element's stable identity
  referentialForm?: string; // FOR_MODEL token, when the mention marks one
  spokenForm: string; // what the Guide should SAY for this mention (form-aware)
  displayName: string; // what the coverage list shows (honors meaning-bearing strips); NEVER a raw code
  source: "aliases" | "prose-gloss" | "withheld" | "unresolved"; // withheld = the B? being (referentialForms.ts)
  resolved: boolean; // false ⇒ no grounded wording; displayName is a safe placeholder, never the code
};

// Shown instead of a raw code when resolution fails — the Guide must never voice a code (Hard Rule #3).
export const UNRESOLVED_LABEL = "(unresolved — needs grounded wording)";

// --- normalized, resolved map (the tracker's view) ------------------------------
export type BeingMention = {
  id: string;
  role: string;
  presence: Presence;
  referentialForm?: string;
} & Resolution;

export type ResolvedRef = { id: string } & Resolution;

export type Scene = {
  id: string;
  verseRange: string;
  kind: string;
  communicativePurpose: string;
  beings: BeingMention[];
  places: ResolvedRef[];
  objects: ResolvedRef[];
  times: ResolvedRef[];
  significantAbsence: string | null;
};

export type AuditEntry = {
  id: string; // "R6"
  kind: string; // "STRUCTURAL_ABSENCE_OF_DIVINE_AGENCY"
  appliesTo: string;
  note: string;
  doNotDecide: boolean; // do_not_decide === true → HARD constraint for the Validator
  requiredInAudit?: boolean;
  sourceInMeaningMap?: string;
  carriesForwardTo?: string;
};

export type Level1 = {
  arc: string[];
  context: string[];
  tone: string[];
  pace: string[];
  communicativeFunction: string[];
};

export type ParsedMap = {
  pericopeId: string; // "P01"
  reference: string; // header.bcv
  title: string;
  register: string;
  level1: Level1;
  scenes: Scene[];
  preservationRules: AuditEntry[]; // the do_not_decide audit entries (Validator hard constraints)
  audit: AuditEntry[]; // the full high_risk_register_audit
};

// --- coverage elements (the flat, independently-trackable list) ------------------
export type CoverageStatus = "not_encountered" | "surfaced" | "engaged";
export type CoverageKind =
  | "arc" | "context" | "tone" | "function"
  | "scene" | "being" | "place" | "object" | "time"
  | "significant_absence" | "preserved_element";

export type CoverageElement = {
  id: string; // stable key, e.g. "being:S4:B3"
  kind: CoverageKind;
  label: string; // human-facing (resolved name / short phrase) — never a raw code
  sceneId?: string;
  detail?: string; // teaching prose or token list
  code?: string; // underlying ID, for matching (never voiced)
  role?: string; // a being's role_in_scene token (e.g. REDEEMER_KIN) — for telling apart two beings who share a role noun in one scene
  hardConstraint?: boolean; // backed by a do_not_decide rule
  relatedAudit?: string[]; // audit ids folded into this element (de-dup)
  unresolved?: boolean; // code had no grounded wording — label is a placeholder, not a name
  status: CoverageStatus;
};
