import { invoke } from "@tauri-apps/api/core";
import type { CandidateAudit, Catalogue, Lookup, Position, ReleaseComparison, Stability } from "./model";
import { readAuditFilter, type AuditFilter } from "./projection-audit";

const SCHEMA = "transit-atlas.study";
const VERSION = 1;
const MODEL = "host-split-zscore-pca-v1";

export interface StudyCamera {
  position: Position;
  target: Position;
  focused: boolean;
}

export type StudyView =
  | { kind: "catalogue" }
  | { kind: "projection"; filter: AuditFilter }
  | { kind: "uncertainty"; scenario: number }
  | { kind: "release"; release: "DR24" | "Cumulative" };

export interface StudySelection {
  candidate: string;
  neighbour: string;
  view: StudyView;
  camera: StudyCamera | null;
}

function evidence(
  catalogue: Catalogue,
  nominal: Lookup,
  visible: Lookup,
  uncertainty?: Stability,
  comparison?: ReleaseComparison,
  audit?: CandidateAudit,
) {
  return {
    feature_metadata: catalogue.features,
    variance_ratios: catalogue.variance_ratios,
    query: visible.query,
    neighbours: visible.neighbours,
    ...(audit ? { projection_audit: audit } : {}),
    context_points: uncertainty ? [
      { id: "catalogue", position: nominal.query.position, nearest: nominal.neighbours[0].observation.koi_id },
      ...uncertainty.scenarios.map((trial, index) => ({
        id: `scenario-${index + 1}`,
        position: trial.position,
        nearest: trial.neighbours[0].observation.koi_id,
      })),
    ] : comparison ? [
      { id: "DR24", position: comparison.earlier_query.position, nearest: comparison.earlier_nearest },
      { id: "Cumulative", position: nominal.query.position, nearest: comparison.current_nearest },
    ] : [],
  };
}

export function makeStudy(
  selection: StudySelection,
  catalogue: Catalogue,
  nominal: Lookup,
  visible: Lookup,
  uncertainty?: Stability,
  comparison?: ReleaseComparison,
  audit?: CandidateAudit,
) {
  return {
    schema: SCHEMA,
    version: VERSION,
    model: MODEL,
    saved_at: new Date().toISOString(),
    provenance: {
      catalogue: catalogue.snapshot,
      variation_sha256: uncertainty?.source_sha256 ?? comparison?.source_sha256 ?? null,
    },
    selection,
    evidence: evidence(catalogue, nominal, visible, uncertainty, comparison, audit),
  };
}

export const saveStudyFile = (study: ReturnType<typeof makeStudy>) =>
  invoke<string | null>("save_study", { document: JSON.stringify(study, null, 2) + "\n" });

export const openStudyFile = () => invoke<string | null>("open_study");

function record(value: unknown): Record<string, unknown> {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  throw new Error("The study contains an invalid object.");
}

function koi(value: unknown): value is string {
  return typeof value === "string" && /^K\d{5}\.\d{2}$/.test(value) && value.length === 9;
}

function digest(value: unknown): value is string {
  return typeof value === "string" && /^[a-f0-9]{64}$/.test(value) && value.length === 64;
}

function position(value: unknown): value is Position {
  return Array.isArray(value) && value.length === 3 && value.every((axis) =>
    typeof axis === "number" && Number.isFinite(axis) && Math.abs(axis) <= 10_000);
}

function readCamera(value: unknown): StudyCamera | null {
  if (value === null) return null;
  const { position: origin, target, focused } = record(value);
  if (position(origin) && position(target) && typeof focused === "boolean") {
    const distance = Math.hypot(...origin.map((axis, index) => axis - target[index]));
    if (distance >= (focused ? 0.18 : 0.65) - 1e-8 && distance <= 110 + 1e-8) {
      return { position: origin, target, focused };
    }
  }
  throw new Error("The study has an invalid 3D camera view.");
}

function readView(value: unknown): StudyView {
  const { kind, scenario, release, filter } = record(value);
  if (kind === "catalogue") return { kind };
  if (kind === "uncertainty" && typeof scenario === "number" &&
      Number.isSafeInteger(scenario) && scenario >= 0) return { kind, scenario };
  if (kind === "release" && (release === "DR24" || release === "Cumulative")) return { kind, release };
  const auditFilter = readAuditFilter(filter);
  if (kind === "projection" && auditFilter) return { kind, filter: auditFilter };
  throw new Error("The study has an invalid investigation view.");
}

export function parseStudy(document: string) {
  const data = record(JSON.parse(document));
  if (data.schema !== SCHEMA || data.version !== VERSION || data.model !== MODEL) {
    throw new Error("This study uses an unsupported version or model.");
  }
  const { candidate, neighbour, view, camera } = record(data.selection);
  if (!koi(candidate) || !koi(neighbour)) {
    throw new Error("The study contains an invalid candidate or neighbour ID.");
  }
  const provenance = record(data.provenance);
  const catalogue = record(provenance.catalogue);
  if (!digest(catalogue.sha256) ||
      (provenance.variation_sha256 !== null && !digest(provenance.variation_sha256))) {
    throw new Error("The study is missing valid data fingerprints.");
  }
  return {
    catalogue,
    variationSha256: provenance.variation_sha256,
    selection: { candidate, neighbour, view: readView(view), camera: readCamera(camera) },
    evidence: record(data.evidence),
  };
}

function matches(actual: unknown, expected: unknown): boolean {
  if (typeof expected === "number") {
    return typeof actual === "number" && Number.isFinite(actual) &&
      Math.abs(actual - expected) <= 1e-8 * Math.max(Math.abs(expected), 1);
  }
  if (Array.isArray(expected)) {
    return Array.isArray(actual) && actual.length === expected.length &&
      expected.every((value, index) => matches(actual[index], value));
  }
  if (expected !== null && typeof expected === "object") {
    if (actual === null || typeof actual !== "object" || Array.isArray(actual)) return false;
    const entries = Object.entries(expected);
    return Object.keys(actual).length === entries.length && entries.every(([key, value]) =>
      Object.hasOwn(actual, key) && matches((actual as Record<string, unknown>)[key], value));
  }
  return actual === expected;
}

export function checkStudy(
  file: ReturnType<typeof parseStudy>,
  catalogue: Catalogue,
  nominal: Lookup,
  visible: Lookup,
  uncertainty?: Stability,
  comparison?: ReleaseComparison,
  audit?: CandidateAudit,
) {
  if (file.catalogue.sha256 !== catalogue.snapshot.sha256) {
    throw new Error("This study was saved with a different Kepler catalogue snapshot.");
  }
  if (file.variationSha256 !== (uncertainty?.source_sha256 ?? comparison?.source_sha256 ?? null)) {
    throw new Error("This study uses a different set of uncertainty or release measurements.");
  }
  if (!matches(file.catalogue, catalogue.snapshot) ||
      !matches(file.evidence, evidence(catalogue, nominal, visible, uncertainty, comparison, audit))) {
    throw new Error("The saved evidence differs from the current calculation.");
  }
  const rank = visible.neighbours.findIndex(({ observation }) => observation.koi_id === file.selection.neighbour);
  if (rank === -1) throw new Error("The selected neighbour is missing from the verified ranking.");
  return rank;
}
