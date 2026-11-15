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
