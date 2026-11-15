use serde::Serialize;

use super::{
    squared_deltas, stability::Measurement, Atlas, Neighbour, Observation, Vector, FEATURE_COUNT,
};

const RELATIVE_GAP_TOLERANCE: f64 = 1e-12;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ExactStatus {
    Stable,
    Changed,
    NearTie,
}

#[derive(Serialize)]
pub struct ExactSensitivity<'a> {
    pub query: &'a str,
    source_date: &'a str,
    source_sha256: &'a str,
    pub eligible_references: usize,
    pub nominal_nearest: &'a str,
    pub status: ExactStatus,
    pub challenger: &'a str,
    pub minimum_gap: f64,
    tolerance: f64,
    nominal_gap: f64,
    measurements: Vec<Measurement>,
    pub witness: Option<Witness<'a>>,
}

#[derive(Serialize)]
pub struct Witness<'a> {
    query: Observation,
    neighbours: Vec<Neighbour<'a>>,
}

impl Witness<'_> {
    pub fn nearest(&self) -> &str {
        &self.neighbours[0].observation.koi_id
    }
}

struct Corner<'a> {
    challenger: &'a str,
    values: Vector,
    gap: f64,
    tolerance: f64,
    nominal_gap: f64,
}

fn minimum_corner(a: &Vector, b: &Vector, low: &Vector, high: &Vector) -> Vector {
    std::array::from_fn(|i| if a[i] >= b[i] { low[i] } else { high[i] })
}

fn score(vector: &Vector, reference: &Vector) -> f64 {
    squared_deltas(vector, reference).into_iter().sum()
}

impl Atlas {
    pub fn exact_sensitivity(&self, query_id: &str) -> Result<ExactSensitivity<'_>, String> {
        let index = self.candidate_index(query_id)?;
        let query = &self.catalogue.observations[index];
        let bounds = self.quoted_bounds(&query.koi_id)?;
        let intervals: [[f64; 2]; FEATURE_COUNT] =
            std::array::from_fn(|i| bounds[i].unwrap_or([query.values[i]; 2]));
        for ([low, _], feature) in intervals.iter().zip(&self.catalogue.features) {
            if feature.log10 && *low <= 0.0 {
                return Err(format!(
                    "{} needs a positive lower bound for {} to check exact bounds.",
                    query.koi_id, feature.name,
                ));
            }
        }
        let low_values = intervals.map(|[low, _]| low);
        let high_values = intervals.map(|[_, high]| high);
        let low = Self::scale(&self.catalogue.features, &low_values);
        let high = Self::scale(&self.catalogue.features, &high_values);
        let (eligible, _) = self.eligible_references(query.host_id);
        let nominal = self.nearest(&self.scaled[index], &eligible)?;
        let winner = nominal[0].observation;
        // Neighbours borrow directly from the KOI-sorted catalogue.
        let winner_index = self
            .catalogue
            .observations
            .binary_search_by(|row| row.koi_id.cmp(&winner.koi_id))
            .map_err(|_| "The nominal nearest reference is unavailable.")?;
        let a = &self.scaled[winner_index];

        let mut minimum = None::<Corner<'_>>;
        let mut change = None::<Corner<'_>>;
        let mut near_tie = None::<Corner<'_>>;
        for &other in &eligible {
            if other == winner_index {
                continue;
            }
            let b = &self.scaled[other];
            let corner = minimum_corner(a, b, &low, &high);
            let winner_distance = score(&corner, a);
            let challenger_distance = score(&corner, b);
            let gap = challenger_distance - winner_distance;
            let tolerance =
                RELATIVE_GAP_TOLERANCE * winner_distance.max(challenger_distance).max(1.0);
            let target = if gap < -tolerance {
                &mut change
            } else if gap <= tolerance {
                &mut near_tie
            } else {
                &mut minimum
            };
            if target.as_ref().is_none_or(|best| gap < best.gap) {
                *target = Some(Corner {
                    challenger: &self.catalogue.observations[other].koi_id,
                    values: minimum_corner(a, b, &low_values, &high_values),
                    gap,
                    tolerance,
                    nominal_gap: score(&self.scaled[index], b) - nominal[0].distance_squared,
                });
            }
        }

        let (limiting, status, witness) = if let Some(limiting) = change {
            let scaled = Self::scale(&self.catalogue.features, &limiting.values);
            let neighbours = self.nearest(&scaled, &eligible)?;
            if neighbours[0].observation.koi_id == winner.koi_id {
                return Err("The witness did not reproduce a ranking change.".into());
            }
            let witness = Witness {
                query: Observation {
                    values: limiting.values,
                    position: self.catalogue.projection.project(&scaled),
                    ..query.clone()
                },
                neighbours,
            };
            (limiting, ExactStatus::Changed, Some(witness))
        } else if let Some(limiting) = near_tie {
            (limiting, ExactStatus::NearTie, None)
        } else {
            let limiting = minimum.ok_or("No challenger reference is available.")?;
            (limiting, ExactStatus::Stable, None)
        };

        Ok(ExactSensitivity {
            query: &query.koi_id,
            source_date: &self.uncertainty.retrieved_utc_date,
            source_sha256: &self.uncertainty.source_sha256,
            eligible_references: eligible.len(),
            nominal_nearest: &winner.koi_id,
            status,
            challenger: limiting.challenger,
            minimum_gap: limiting.gap,
            tolerance: limiting.tolerance,
            nominal_gap: limiting.nominal_gap,
            measurements: self.describe_bounds(query.values, bounds),
            witness,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn affine_minimum_matches_all_corners_with_fixed_coordinates_and_ties() {
        let low = [-1.0, 1.0, 0.5, 3.0, 0.0, 0.0, 0.0, 0.0];
        let high = [2.0, 1.0, 1.5, 4.0, 0.0, 0.0, 0.0, 0.0];
        let a = [0.0, 1.0, 1.0, 2.0, 0.0, 0.0, 0.0, 0.0];
        for b in [
            a,
            [3.0; 8],
            [-2.0; 8],
            [1.0, 1.0, 0.0, 4.0, 0.0, 0.0, 0.0, 0.0],
        ] {
            let gap = |point: &Vector| score(point, &b) - score(point, &a);
            let exhaustive = (0..(1 << FEATURE_COUNT))
                .map(|mask| {
                    gap(&std::array::from_fn(|i| {
                        if mask & (1 << i) == 0 {
                            low[i]
                        } else {
                            high[i]
                        }
                    }))
                })
                .min_by(f64::total_cmp)
                .unwrap();
            assert_eq!(gap(&minimum_corner(&a, &b, &low, &high)), exhaustive);
        }
    }

    #[test]
    fn verifies_witness_missed_by_the_scenarios() {
        let atlas = Atlas::load().unwrap();
        assert_eq!(atlas.stability("K00100.01").unwrap().same_first, 64);
        let report = atlas.exact_sensitivity("K00100.01").unwrap();
        assert_eq!(report.status, ExactStatus::Changed);
        assert_eq!(report.eligible_references, 5783);
        assert_eq!(report.nominal_nearest, "K03457.01");
        assert_eq!(report.challenger, "K00121.01");
        assert!((report.minimum_gap - (-0.516418)).abs() < 1e-6);
        let witness = report.witness.unwrap();
        assert_eq!(witness.nearest(), "K00121.01");
        for (value, measurement) in witness.query.values.iter().zip(report.measurements) {
            let [low, high] = measurement.bounds.unwrap_or([measurement.original; 2]);
            assert!((low..=high).contains(value));
        }
        assert!(witness
            .neighbours
            .iter()
            .all(|row| row.observation.host_id != witness.query.host_id));
    }

    #[test]
    fn certifies_a_stable_reference_and_reports_a_log_boundary() {
        let atlas = Atlas::load().unwrap();
        let stable = atlas.exact_sensitivity("K00099.01").unwrap();
        assert_eq!(stable.status, ExactStatus::Stable);
        assert!((stable.minimum_gap - 0.5076839249285761).abs() < 1e-9);
        assert!(stable.witness.is_none());
        assert!(atlas
            .exact_sensitivity("K00304.02")
            .err()
            .unwrap()
            .contains("positive lower bound for Transit duration"));
    }

    #[test]
    fn treats_equal_reference_distances_as_a_boundary() {
        let mut atlas = Atlas::load().unwrap();
        let index = atlas.candidate_index("K00099.01").unwrap();
        let (eligible, _) = atlas.eligible_references(atlas.catalogue.observations[index].host_id);
        let nominal = atlas.lookup("K00099.01").unwrap();
        let winner = eligible
            .iter()
            .copied()
            .find(|&i| {
                atlas.catalogue.observations[i].koi_id == nominal.neighbours[0].observation.koi_id
            })
            .unwrap();
        let duplicate = *eligible.iter().find(|&&i| i != winner).unwrap();
        atlas.scaled[duplicate] = atlas.scaled[winner];

        let report = atlas.exact_sensitivity("K00099.01").unwrap();
        assert_eq!(report.status, ExactStatus::NearTie);
        let expected = winner.min(duplicate);
        assert_eq!(
            report.nominal_nearest,
            atlas.catalogue.observations[expected].koi_id
        );
        assert_eq!(report.minimum_gap, 0.0);
        assert!(report.witness.is_none());
    }
}
