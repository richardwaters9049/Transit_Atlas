import { invoke } from "@tauri-apps/api/core";
import type {
  CandidateAudit,
  Catalogue,
  ExactSensitivity,
  LightCurveDocument,
  Lookup,
  Position,
  ReleaseComparison,
  Stability,
} from "./model";
import { readAuditFilter, type AuditFilter } from "./projection-audit";

const SCHEMA = "transit-atlas.study";
const VERSION = 2;
const MODEL = "host-split-zscore-pca-v1";

export interface StudyCamera {
  position: Position;
  target: Position;
  focused: boolean;
}

export type StudyView =
  | { kind: "catalogue" }
  | { kind: "projection"; filter: AuditFilter }
  | { kind: "exact"; witness: boolean }
  | { kind: "uncertainty"; scenario: number }
  | { kind: "release"; release: "DR24" | "Cumulative" };

export interface StudySelection {
  candidate: string;
  neighbour: string;
  view: StudyView;
  camera: StudyCamera | null;
}

export interface StudyLightCurveProvenance {
  identity: {
    koi_id: string;
    host_id: number;
    signal_role: "candidate" | "reference";
  };
  product: {
    archive: string;
    mission: string;
    data_uri: string;
    product_filename: string;
    source_sha256: string;
    source_bytes: number;
    author: string;
    quarter: number;
    data_release: number;
    cadence: string;
    time_format: string;
    time_scale: string;
    time_unit: string;
    flux_unit: string;
  };
  ephemeris: {
    period_days: number;
    epoch_bkjd: number;
    duration_hours: number;
    epoch_definition: string;
  };
  processing_fingerprint: string;
}

function evidence(
  catalogue: Catalogue,
  nominal: Lookup,
  visible: Lookup,
  uncertainty?: Stability,
  comparison?: ReleaseComparison,
  audit?: CandidateAudit,
  exact?: ExactSensitivity,
) {
  return {
    feature_metadata: catalogue.features,
    variance_ratios: catalogue.variance_ratios,
    query: visible.query,
    neighbours: visible.neighbours,
    ...(audit ? { projection_audit: audit } : {}),
    ...(exact ? { exact_sensitivity: exact } : {}),
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
    ] : exact?.witness ? [
      { id: "catalogue", position: nominal.query.position, nearest: exact.nominal_nearest },
      { id: "witness", position: exact.witness.query.position, nearest: exact.witness.neighbours[0].observation.koi_id },
    ] : [],
  };
}

export function studyLightCurve(document: LightCurveDocument): StudyLightCurveProvenance {
  const { identity, source, ephemeris, processing_fingerprint: fingerprint } = document;
  return readStudyLightCurve({
    identity: {
      koi_id: identity.koi_id,
      host_id: identity.host_id,
      signal_role: identity.signal_role,
    },
    product: {
      archive: source.archive,
      mission: source.mission,
      data_uri: source.data_uri,
      product_filename: source.product_filename,
      source_sha256: source.sha256,
      source_bytes: source.bytes,
      author: source.author,
      quarter: source.quarter,
      data_release: source.data_release,
      cadence: source.cadence,
      time_format: source.time_format,
      time_scale: source.time_scale,
      time_unit: source.time_unit,
      flux_unit: source.flux_unit,
    },
    ephemeris: {
      period_days: ephemeris.period_days,
      epoch_bkjd: ephemeris.epoch_bkjd,
      duration_hours: ephemeris.duration_hours,
      epoch_definition: ephemeris.epoch_definition,
    },
    processing_fingerprint: fingerprint,
  });
}

export function makeStudy(
  selection: StudySelection,
  catalogue: Catalogue,
  nominal: Lookup,
  visible: Lookup,
  uncertainty?: Stability,
  comparison?: ReleaseComparison,
  audit?: CandidateAudit,
  exact?: ExactSensitivity,
  lightCurves: LightCurveDocument[] = [],
) {
  const lightCurveProvenance = lightCurves.map(studyLightCurve);
  validateLightCurveSelection(lightCurveProvenance, selection.candidate, selection.neighbour);
  return {
    schema: SCHEMA,
    version: VERSION,
    model: MODEL,
    saved_at: new Date().toISOString(),
    provenance: {
      catalogue: catalogue.snapshot,
      variation_sha256: uncertainty?.source_sha256 ?? comparison?.source_sha256 ?? exact?.source_sha256 ?? null,
      light_curves: lightCurveProvenance,
    },
    selection,
    evidence: evidence(catalogue, nominal, visible, uncertainty, comparison, audit, exact),
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

function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function nonEmpty(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function readStudyLightCurve(value: unknown): StudyLightCurveProvenance {
  const { identity, product, ephemeris, processing_fingerprint: fingerprint } = record(value);
  const parsedIdentity = record(identity);
  const parsedProduct = record(product);
  const parsedEphemeris = record(ephemeris);
  const {
    koi_id: koiId,
    host_id: hostId,
    signal_role: role,
  } = parsedIdentity;
  const {
    archive, mission, data_uri: dataUri, product_filename: filename,
    source_sha256: sourceSha, source_bytes: sourceBytes, author,
    quarter, data_release: dataRelease, cadence, time_format: timeFormat,
    time_scale: timeScale, time_unit: timeUnit, flux_unit: fluxUnit,
  } = parsedProduct;
  const {
    period_days: period, epoch_bkjd: epoch, duration_hours: duration,
    epoch_definition: epochDefinition,
  } = parsedEphemeris;

  if (!koi(koiId) || !Number.isSafeInteger(hostId) || (hostId as number) <= 0 ||
      (role !== "candidate" && role !== "reference") ||
      !nonEmpty(archive) || !nonEmpty(mission) || !nonEmpty(dataUri) || !nonEmpty(filename) ||
      !digest(sourceSha) || !Number.isSafeInteger(sourceBytes) || (sourceBytes as number) <= 0 ||
      !nonEmpty(author) || !Number.isSafeInteger(quarter) || (quarter as number) <= 0 ||
      !Number.isSafeInteger(dataRelease) || (dataRelease as number) <= 0 ||
      !nonEmpty(cadence) || !nonEmpty(timeFormat) || !nonEmpty(timeScale) ||
      !nonEmpty(timeUnit) || !nonEmpty(fluxUnit) ||
      !finite(period) || period <= 0 || !finite(epoch) ||
      !finite(duration) || duration <= 0 || !nonEmpty(epochDefinition) || !digest(fingerprint)) {
    throw new Error("The study contains invalid Kepler light-curve provenance.");
  }

  return {
    identity: { koi_id: koiId, host_id: hostId as number, signal_role: role },
    product: {
      archive, mission, data_uri: dataUri, product_filename: filename,
      source_sha256: sourceSha, source_bytes: sourceBytes as number,
      author, quarter: quarter as number, data_release: dataRelease as number,
      cadence, time_format: timeFormat, time_scale: timeScale, time_unit: timeUnit, flux_unit: fluxUnit,
    },
    ephemeris: {
      period_days: period, epoch_bkjd: epoch, duration_hours: duration,
      epoch_definition: epochDefinition,
    },
    processing_fingerprint: fingerprint,
  };
}

function validateLightCurveSelection(
  lightCurves: StudyLightCurveProvenance[],
  candidate: string,
  neighbour: string,
) {
  if (lightCurves.length > 2) throw new Error("A study cannot contain more than two selected light curves.");
  const roles = new Set<string>();
  for (const lightCurve of lightCurves) {
    const { koi_id: koiId, signal_role: role } = lightCurve.identity;
    if (roles.has(role)) throw new Error("A study contains duplicate Kepler light-curve roles.");
    roles.add(role);
    if ((role === "candidate" && koiId !== candidate) ||
        (role === "reference" && koiId !== neighbour)) {
      throw new Error("A saved Kepler light curve does not match the study selection.");
    }
  }
  if (candidate === "K00115.03" && !roles.has("candidate")) {
    throw new Error("The study is missing the selected candidate light-curve product.");
  }
  if (candidate === "K00115.03" && neighbour === "K02961.01" && !roles.has("reference")) {
    throw new Error("The study is missing the selected reference light-curve product.");
  }
}

function readStudyLightCurves(value: unknown, candidate: string, neighbour: string) {
  if (!Array.isArray(value)) throw new Error("The study is missing its Kepler light-curve provenance list.");
  const lightCurves = value.map(readStudyLightCurve);
  validateLightCurveSelection(lightCurves, candidate, neighbour);
  return lightCurves;
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
  const { kind, scenario, release, filter, witness } = record(value);
  if (kind === "catalogue") return { kind };
  if (kind === "uncertainty" && typeof scenario === "number" &&
      Number.isSafeInteger(scenario) && scenario >= 0) return { kind, scenario };
  if (kind === "release" && (release === "DR24" || release === "Cumulative")) return { kind, release };
  const auditFilter = readAuditFilter(filter);
  if (kind === "projection" && auditFilter) return { kind, filter: auditFilter };
  if (kind === "exact" && typeof witness === "boolean") return { kind, witness };
  throw new Error("The study has an invalid investigation view.");
}

export function parseStudy(document: string) {
  const data = record(JSON.parse(document));
  if (data.schema !== SCHEMA || (data.version !== 1 && data.version !== VERSION) || data.model !== MODEL) {
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
  const lightCurves = data.version === 1
    ? null
    : readStudyLightCurves(provenance.light_curves, candidate, neighbour);
  return {
    catalogue,
    variationSha256: provenance.variation_sha256,
    lightCurves,
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
  exact?: ExactSensitivity,
  lightCurves: StudyLightCurveProvenance[] = [],
) {
  if (file.catalogue.sha256 !== catalogue.snapshot.sha256) {
    throw new Error("This study was saved with a different Kepler catalogue snapshot.");
  }
  if (file.variationSha256 !== (uncertainty?.source_sha256 ?? comparison?.source_sha256 ?? exact?.source_sha256 ?? null)) {
    throw new Error("This study uses a different set of uncertainty or release measurements.");
  }
  if (file.lightCurves !== null && !matches(file.lightCurves, lightCurves)) {
    throw new Error("The saved Kepler light-curve products or processing fingerprints differ from the current replay.");
  }
  if (!matches(file.catalogue, catalogue.snapshot) ||
      !matches(file.evidence, evidence(catalogue, nominal, visible, uncertainty, comparison, audit, exact))) {
    throw new Error("The saved evidence differs from the current calculation.");
  }
  const rank = visible.neighbours.findIndex(({ observation }) => observation.koi_id === file.selection.neighbour);
  if (rank === -1) throw new Error("The selected neighbour is missing from the verified ranking.");
  return rank;
}
