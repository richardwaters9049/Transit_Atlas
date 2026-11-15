use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use super::{Atlas, Neighbour, Vector, FEATURE_COUNT};

const TRIALS: usize = 64;
const BASES: [usize; FEATURE_COUNT] = [2, 3, 5, 7, 11, 13, 17, 19];
type Bounds = [Option<[f64; 2]>; FEATURE_COUNT];

#[derive(Deserialize)]
pub(super) struct Uncertainties {
    retrieved_utc_date: String,
    source_sha256: String,
    ranges: BTreeMap<String, Bounds>,
}

#[derive(Serialize)]
pub struct Stability<'catalogue> {
    pub query: String,
    pub source_date: String,
    pub source_sha256: String,
    pub trials: usize,
    pub eligible_references: usize,
    pub same_top_five: usize,
    pub same_first: usize,
    pub baseline: Vec<Occurrence>,
    pub replacements: Vec<Occurrence>,
    pub replacement_count: usize,
    pub measurements: Vec<Measurement>,
    pub scenarios: Vec<Scenario<'catalogue>>,
}

#[derive(Serialize)]
pub struct Scenario<'catalogue> {
    pub position: [f64; 3],
    pub values: Vector,
    neighbours: Vec<Neighbour<'catalogue>>,
    pub same_top_five: bool,
    pub same_first: bool,
}

#[derive(Serialize)]
pub struct Occurrence {
    pub koi_id: String,
    pub appearances: usize,
}

#[derive(Serialize)]
pub struct Measurement {
    pub name: String,
    pub unit: String,
    pub original: f64,
    pub bounds: Option<[f64; 2]>,
}

fn radical_inverse(mut number: usize, base: usize) -> f64 {
    let mut value = 0.0;
    let mut factor = 1.0 / base as f64;
    while number > 0 {
        value += (number % base) as f64 * factor;
        number /= base;
        factor /= base as f64;
    }
    value
}

impl Atlas {
    pub fn stability(&self, query_id: &str) -> Result<Stability<'_>, String> {
        let index = self.candidate_index(query_id)?;
        let query = &self.catalogue.observations[index];
        let bounds = self.uncertainty.ranges.get(&query.koi_id).ok_or_else(|| {
            format!(
                "No usable quoted measurement ranges are available for {}.",
                query.koi_id
            )
        })?;
        let (eligible, _) = self.eligible_references(query.host_id);
        let baseline = self.nearest(&self.scaled[index], &eligible)?;
        let baseline_ids: Vec<_> = baseline
            .iter()
            .map(|row| row.observation.koi_id.as_str())
            .collect();
        let mut occurrences = BTreeMap::new();
        let mut same_top_five = 0;
        let mut same_first = 0;
        let mut scenarios = Vec::with_capacity(TRIALS);

        for trial in 1..=TRIALS {
            let sample = std::array::from_fn(|feature| {
                if let Some([low, high]) = bounds[feature] {
                    low + (high - low) * radical_inverse(trial, BASES[feature])
                } else {
                    query.values[feature]
                }
            });
            let scaled = Self::scale(&self.catalogue.features, &sample);
            let ranking = self.nearest(&scaled, &eligible)?;
            let mut retained = true;
            let first_retained = ranking[0].observation.koi_id == baseline_ids[0];
            for row in &ranking {
                let koi_id = row.observation.koi_id.as_str();
                *occurrences.entry(koi_id).or_insert(0) += 1;
                retained &= baseline_ids.contains(&koi_id);
            }
            same_top_five += usize::from(retained);
            same_first += usize::from(first_retained);
            scenarios.push(Scenario {
                position: self.catalogue.projection.project(&scaled),
                values: sample,
                neighbours: ranking,
                same_top_five: retained,
                same_first: first_retained,
            });
        }

        let baseline = baseline_ids
            .into_iter()
            .map(|koi_id| Occurrence {
                koi_id: koi_id.to_owned(),
                appearances: occurrences.remove(koi_id).unwrap_or(0),
            })
            .collect();
        let mut replacements: Vec<_> = occurrences
            .into_iter()
            .map(|(koi_id, appearances)| Occurrence {
                koi_id: koi_id.to_owned(),
                appearances,
            })
            .collect();
        replacements.sort_by(|left, right| {
            right
                .appearances
                .cmp(&left.appearances)
                .then_with(|| left.koi_id.cmp(&right.koi_id))
        });
        let replacement_count = replacements.len();
        replacements.truncate(3);
        Ok(Stability {
            query: query.koi_id.clone(),
            source_date: self.uncertainty.retrieved_utc_date.clone(),
            source_sha256: self.uncertainty.source_sha256.clone(),
            trials: TRIALS,
            eligible_references: eligible.len(),
            same_top_five,
            same_first,
            baseline,
            replacements,
            replacement_count,
            scenarios,
            measurements: self
                .catalogue
                .features
                .iter()
                .zip(query.values)
                .zip(*bounds)
                .map(|((feature, original), bounds)| Measurement {
                    name: feature.name.clone(),
                    unit: feature.unit.clone(),
                    original,
                    bounds,
                })
                .collect(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keeps_a_fixed_feature_and_repeats_real_scenarios() {
        let atlas = Atlas::load().unwrap();
        let first = atlas.stability("K00115.03").unwrap();
        let second = atlas.stability("k00115.03").unwrap();
        assert_eq!(first.eligible_references, 5781);
        assert_eq!(first.trials, 64);
        assert_eq!(
            first
                .measurements
                .iter()
                .filter(|item| item.bounds.is_some())
                .count(),
            7
        );
        assert!(first.measurements[4].bounds.is_none());
        assert_eq!(first.baseline[0].koi_id, "K02961.01");
        assert!(first.same_top_five < first.trials);
        assert!(first.replacement_count > 0);
        assert_eq!(
            serde_json::to_value(first).unwrap(),
            serde_json::to_value(second).unwrap()
        );
        assert!(atlas.stability("K00115.01").is_err());
    }

    #[test]
    fn generated_fractions_are_strictly_inside_the_interval() {
        for base in BASES {
            for trial in 1..=TRIALS {
                assert!((0.0..1.0).contains(&radical_inverse(trial, base)));
                assert!(radical_inverse(trial, base) > 0.0);
            }
        }
    }

    #[test]
    fn projects_into_the_frozen_catalogue_space_and_explains_each_trial() {
        let atlas = Atlas::load().unwrap();
        let candidate = atlas.candidate_index("K00115.03").unwrap();
        let query = &atlas.catalogue.observations[candidate];
        let expected = atlas.catalogue.projection.project(&atlas.scaled[candidate]);
        for (actual, exported) in expected.into_iter().zip(query.position) {
            assert!((actual - exported).abs() < 1e-7);
        }

        let report = atlas.stability("K00115.03").unwrap();
        assert_eq!(report.scenarios.len(), 64);
        assert_eq!(
            report.scenarios.iter().filter(|row| row.same_first).count(),
            16
        );
        assert_eq!(
            report
                .scenarios
                .iter()
                .filter(|row| row.same_top_five)
                .count(),
            0
        );
        assert!(report
            .scenarios
            .iter()
            .any(|row| row.neighbours[0].observation.koi_id != "K02961.01"));
        for scenario in &report.scenarios {
            assert!(scenario.position.iter().all(|value| value.is_finite()));
            assert_eq!(scenario.values[4], query.values[4]);
            for neighbour in &scenario.neighbours {
                assert_ne!(neighbour.observation.host_id, query.host_id);
                assert!(
                    (neighbour.squared_deltas.iter().sum::<f64>() - neighbour.distance_squared)
                        .abs()
                        < 1e-12
                );
            }
        }
    }
}
