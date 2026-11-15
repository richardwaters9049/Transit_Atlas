use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

mod stability;
pub use stability::Stability;
mod release;
pub use release::ReleaseComparison;
mod projection_audit;
pub use projection_audit::ProjectionAudit;

const FEATURE_COUNT: usize = 8;
const K: usize = 5;
const CATALOGUE: &str = include_str!("../../../data/generated/catalogue.json");
type Vector = [f64; FEATURE_COUNT];

fn squared_deltas<const N: usize>(left: &[f64; N], right: &[f64; N]) -> [f64; N] {
    std::array::from_fn(|axis| {
        let delta = left[axis] - right[axis];
        delta * delta
    })
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Feature {
    field: String,
    name: String,
    unit: String,
    log10: bool,
    mean: f64,
    scale: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Observation {
    koi_id: String,
    host_id: u32,
    disposition: Disposition,
    values: Vector,
    position: [f64; 3],
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Serialize)]
#[serde(rename_all = "UPPERCASE")]
enum Disposition {
    Candidate,
    Confirmed,
    #[serde(rename = "FALSE POSITIVE")]
    FalsePositive,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct Catalogue {
    default_query: String,
    snapshot: Snapshot,
    training_references: usize,
    validation_hosts: usize,
    distance_threshold: f64,
    features: [Feature; FEATURE_COUNT],
    variance_ratios: [f64; 3],
    projection: Projection,
    teaching_example: TeachingExample,
    observations: Vec<Observation>,
}

#[derive(Debug, Deserialize, Serialize)]
struct Projection {
    mean: Vector,
    components: [Vector; 3],
}

impl Projection {
    fn project(&self, scaled: &Vector) -> [f64; 3] {
        self.components.map(|component| {
            (0..FEATURE_COUNT)
                .map(|index| (scaled[index] - self.mean[index]) * component[index])
                .sum()
        })
    }
}

#[derive(Debug, Deserialize, Serialize)]
struct Snapshot {
    retrieved_utc_date: String,
    doi: String,
    rows: usize,
    sha256: String,
}

#[derive(Debug, Deserialize, Serialize)]
struct TeachingExample {
    full_order: Vec<String>,
    display_order: Vec<String>,
    examples: BTreeMap<String, TeachingPoint>,
}

#[derive(Debug, Deserialize, Serialize)]
struct TeachingPoint {
    vector: Vector,
    full_distance: f64,
    display_distance: f64,
    feature_squared_deltas: Vector,
}

#[derive(Debug, Serialize)]
pub struct Lookup<'catalogue> {
    query: &'catalogue Observation,
    neighbours: Vec<Neighbour<'catalogue>>,
    eligible_references: usize,
    same_host_excluded: usize,
    mixed_dispositions: bool,
    distant: bool,
}

#[derive(Debug, Serialize)]
struct Neighbour<'catalogue> {
    observation: &'catalogue Observation,
    distance: f64,
    distance_squared: f64,
    squared_deltas: Vector,
}

pub struct Atlas {
    catalogue: Catalogue,
    scaled: Vec<Vector>,
    uncertainty: stability::Uncertainties,
    historical: release::HistoricalRelease,
}

impl Atlas {
    pub fn load() -> Result<Self, serde_json::Error> {
        let catalogue: Catalogue = serde_json::from_str(CATALOGUE)?;
        let scaled = catalogue
            .observations
            .iter()
            .map(|observation| Self::scale(&catalogue.features, &observation.values))
            .collect();
        let uncertainty =
            serde_json::from_str(include_str!("../../../data/generated/uncertainties.json"))?;
        let historical = serde_json::from_str(include_str!("../../../data/generated/dr24.json"))?;
        Ok(Self {
            catalogue,
            scaled,
            uncertainty,
            historical,
        })
    }

    pub fn catalogue(&self) -> &Catalogue {
        &self.catalogue
    }

    fn candidate_index(&self, query_id: &str) -> Result<usize, String> {
        let query_id = query_id.trim().to_ascii_uppercase();
        let observations = &self.catalogue.observations;
        let query_index = observations
            .binary_search_by(|row| row.koi_id.as_str().cmp(&query_id))
            .map_err(|_| format!("Unknown or unavailable KOI {query_id}"))?;
        let query = &observations[query_index];
        if query.disposition != Disposition::Candidate {
            return Err(format!(
                "{} is a reference. Choose an unresolved candidate.",
                query.koi_id
            ));
        }
        Ok(query_index)
    }

    fn scale(features: &[Feature; FEATURE_COUNT], values: &Vector) -> Vector {
        std::array::from_fn(|index| {
            let feature = &features[index];
            let value = values[index];
            let transformed = if feature.log10 { value.log10() } else { value };
            (transformed - feature.mean) / feature.scale
        })
    }

    fn eligible_references(&self, host_id: u32) -> (Vec<usize>, usize) {
        let mut same_host_excluded = 0;
        let mut eligible = Vec::new();
        for (index, row) in self.catalogue.observations.iter().enumerate() {
            if row.disposition == Disposition::Candidate {
                continue;
            }
            if row.host_id == host_id {
                same_host_excluded += 1;
                continue;
            }
            eligible.push(index);
        }
        (eligible, same_host_excluded)
    }

    fn nearest(&self, query: &Vector, eligible: &[usize]) -> Result<Vec<Neighbour<'_>>, String> {
        if eligible.len() < K {
            return Err(format!(
                "Only {} eligible reference signals",
                eligible.len()
            ));
        }
        let mut neighbours = Vec::with_capacity(eligible.len());
        for &index in eligible {
            let squared_deltas = squared_deltas(&self.scaled[index], query);
            let distance_squared: f64 = squared_deltas.iter().sum();
            neighbours.push(Neighbour {
                observation: &self.catalogue.observations[index],
                distance: distance_squared.sqrt(),
                distance_squared,
                squared_deltas,
            });
        }
        let compare = |left: &Neighbour, right: &Neighbour| {
            left.distance_squared
                .total_cmp(&right.distance_squared)
                .then_with(|| left.observation.koi_id.cmp(&right.observation.koi_id))
        };
        neighbours.select_nth_unstable_by(K - 1, compare);
        neighbours.truncate(K);
        neighbours.sort_unstable_by(compare);
        Ok(neighbours)
    }

    pub fn lookup(&self, query_id: &str) -> Result<Lookup<'_>, String> {
        let query_index = self.candidate_index(query_id)?;
        let query = &self.catalogue.observations[query_index];
        let (eligible, same_host_excluded) = self.eligible_references(query.host_id);
        let neighbours = self.nearest(&self.scaled[query_index], &eligible)?;
        let eligible_references = eligible.len();
        let mixed_dispositions = neighbours
            .iter()
            .any(|row| row.observation.disposition != neighbours[0].observation.disposition);
        let distant = neighbours[K - 1].distance > self.catalogue.distance_threshold;
        Ok(Lookup {
            query,
            neighbours,
            eligible_references,
            same_host_excluded,
            mixed_dispositions,
            distant,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reproduces_python_fixture() {
        let atlas = Atlas::load().unwrap();
        let actual = atlas.lookup(" k00115.03 ").unwrap();
        let expected: serde_json::Value =
            serde_json::from_str(include_str!("../../../data/fixtures/K00115.03.json")).unwrap();
        assert_eq!(actual.eligible_references, 5781);
        assert_eq!(actual.same_host_excluded, 2);
        assert!(actual.mixed_dispositions);
        let expected_rows = expected["neighbours"].as_array().unwrap();
        assert_eq!(expected_rows.len(), actual.neighbours.len());
        for (row, expected_row) in actual.neighbours.iter().zip(expected_rows) {
            assert_eq!(
                row.observation.koi_id,
                expected_row["koi_id"].as_str().unwrap()
            );
            assert_ne!(row.observation.host_id, actual.query.host_id);
            assert!((row.distance - expected_row["distance"].as_f64().unwrap()).abs() < 1e-12);
            for (feature, delta) in atlas.catalogue.features.iter().zip(row.squared_deltas) {
                let expected_delta = expected_row["feature_contributions"][feature.field.as_str()]
                    ["squared_delta"]
                    .as_f64()
                    .unwrap();
                assert!((delta - expected_delta).abs() < 1e-12, "{}", feature.field);
            }
        }
    }

    #[test]
    fn catalogue_has_only_candidate_queries_and_training_references() {
        let atlas = Atlas::load().unwrap();
        let observations = &atlas.catalogue.observations;
        let candidate_count = observations
            .iter()
            .filter(|row| row.disposition == Disposition::Candidate)
            .count();
        assert_eq!(candidate_count, 1872);
        assert_eq!(
            observations.len() - candidate_count,
            atlas.catalogue.training_references
        );
        assert!(atlas.lookup("K00115.01").is_err());
        assert!(atlas.lookup("K00000.00").is_err());
    }
}
