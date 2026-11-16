import { invoke } from "@tauri-apps/api/core";

export type Disposition = "CANDIDATE" | "CONFIRMED" | "FALSE POSITIVE";
export type Position = [number, number, number];

export interface Observation {
  koi_id: string;
  host_id: number;
  disposition: Disposition;
  values: number[];
  position: Position;
}

export interface Neighbour {
  observation: Observation;
  distance: number;
  distance_squared: number;
  squared_deltas: number[];
}

export interface Lookup {
  query: Observation;
  neighbours: Neighbour[];
  eligible_references: number;
  same_host_excluded: number;
  mixed_dispositions: boolean;
  distant: boolean;
}

interface TeachingPoint {
  vector: number[];
  full_distance: number;
  display_distance: number;
  feature_squared_deltas: number[];
}

export interface Catalogue {
  default_query: string;
  snapshot: { retrieved_utc_date: string; doi: string; rows: number; sha256: string };
  training_references: number;
  validation_hosts: number;
  distance_threshold: number;
  features: { field: string; name: string; unit: string }[];
  variance_ratios: Position;
  observations: Observation[];
  teaching_example: {
    full_order: string[];
    display_order: string[];
    examples: Record<string, TeachingPoint>;
  };
}

export const getCatalogue = () => invoke<Catalogue>("catalogue");

export const getNeighbours = (queryId: string) => invoke<Lookup>("neighbours", { queryId });

export interface FoldedLightCurvePoint {
  phase: number;
  phase_days: number;
  time_bkjd: number;
  relative_flux_ppm: number;
  relative_flux_error_ppm: number | null;
  quality: number;
  cadenceno: number | null;
}

export interface LightCurveDocument {
  schema: "transit-atlas.kepler-lightcurve";
  version: 1;
  processing_fingerprint: string;
  identity: { koi_id: string; host_id: number; signal_role: "candidate" | "reference" };
  ephemeris: {
    period_days: number;
    epoch_bkjd: number;
    duration_hours: number;
    epoch_definition: string;
  };
  source: {
    archive: string;
    mission: string;
    data_uri: string;
    product_filename: string;
    local_file: string;
    sha256: string;
    bytes: number;
    author: string;
    quarter: number;
    data_release: number;
    cadence: string;
    time_format: string;
    time_scale: string;
    time_unit: string;
    flux_unit: string;
    fits_metadata: Record<string, string | number>;
  };
  processing: {
    reader: string;
    reader_version: string;
    flux_column: string;
    quality_bitmask: number;
    quality_rule: string;
    normalization: string;
    phase_convention: string;
    phase_origin: string;
    source_cadences_preserved: boolean;
  };
  folded: {
    normalization: string;
    normalization_median_flux: number;
    quality_bitmask: number;
    cadences_total: number;
    cadences_used: number;
    cadences_quality_rejected: number;
    cadences_invalid_rejected: number;
    transit_half_duration_phase: number;
    points: FoldedLightCurvePoint[];
  };
}

export const getLightCurve = (koiId: string, quarter = 4) =>
  invoke<LightCurveDocument>("light_curve", { koiId, quarter });

export interface ProjectedNeighbour {
  koi_id: string;
  position: Position;
  full_rank: number;
  projected_distance: number;
  full_distance: number;
  omitted_share: number | null;
}

export interface CandidateAudit {
  koi_id: string;
  eligible_references: number;
  shared: number;
  projected_neighbours: ProjectedNeighbour[];
}

export interface ProjectionAudit {
  candidates: CandidateAudit[];
  by_overlap: number[];
  changed_nearest: number;
}

export const getProjectionAudit = () => invoke<ProjectionAudit>("projection_audit");

export interface StabilityOccurrence {
  koi_id: string;
  appearances: number;
}

export interface Stability {
  query: string;
  source_date: string;
  source_sha256: string;
  trials: number;
  eligible_references: number;
  same_top_five: number;
  same_first: number;
  baseline: StabilityOccurrence[];
  replacements: StabilityOccurrence[];
  replacement_count: number;
  measurements: { name: string; unit: string; original: number; bounds: [number, number] | null }[];
  scenarios: Scenario[];
}

export interface Scenario {
  position: Position;
  values: number[];
  neighbours: Neighbour[];
  same_top_five: boolean;
  same_first: boolean;
}

export const getStability = (queryId: string) => invoke<Stability>("stability", { queryId });

export interface ExactSensitivity {
  query: string;
  source_date: string;
  source_sha256: string;
  eligible_references: number;
  nominal_nearest: string;
  status: "stable" | "changed" | "near_tie";
  challenger: string;
  minimum_gap: number;
  tolerance: number;
  nominal_gap: number;
  measurements: Stability["measurements"];
  witness: { query: Observation; neighbours: Neighbour[] } | null;
}

export const getExactSensitivity = (queryId: string) =>
  invoke<ExactSensitivity>("exact_sensitivity", { queryId });

export interface ReleaseComparison {
  release: string;
  source_sha256: string;
  release_last_updated: string;
  retrieved_utc_date: string;
  earlier_query: Observation;
  earlier_neighbours: Neighbour[];
  earlier_nearest: string;
  current_nearest: string;
  retained_neighbours: number;
  standardised_shift: number;
  projected_shift: number;
  standardised_deltas: number[];
}

export const getReleaseComparison = (queryId: string) =>
  invoke<ReleaseComparison>("compare_release", { queryId });

export const dispositionLabels: Record<Disposition, string> = {
  CANDIDATE: "Candidate",
  CONFIRMED: "Confirmed",
  "FALSE POSITIVE": "False positive",
};

export const dispositionColours: Record<Disposition, string> = {
  CANDIDATE: "#b4a4ff",
  CONFIRMED: "#47d5bf",
  "FALSE POSITIVE": "#849ab5",
};
