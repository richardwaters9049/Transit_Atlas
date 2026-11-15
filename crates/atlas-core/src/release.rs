use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use super::{Atlas, Disposition, Neighbour, Observation, Vector};

#[derive(Deserialize)]
pub(super) struct HistoricalRelease {
    release: String,
    release_last_updated: String,
    retrieved_utc_date: String,
    source_sha256: String,
    matches: BTreeMap<String, HistoricalRow>,
}

#[derive(Deserialize)]
struct HistoricalRow {
    host_id: u32,
    disposition: Disposition,
    values: Vector,
}

#[derive(Serialize)]
pub struct ReleaseComparison<'catalogue> {
    pub release: &'catalogue str,
    pub release_last_updated: &'catalogue str,
    pub retrieved_utc_date: &'catalogue str,
    pub source_sha256: &'catalogue str,
    earlier_query: Observation,
    earlier_neighbours: Vec<Neighbour<'catalogue>>,
    pub standardised_shift: f64,
    pub projected_shift: f64,
    standardised_deltas: Vector,
    pub earlier_nearest: &'catalogue str,
    pub current_nearest: &'catalogue str,
    pub retained_neighbours: usize,
}

impl Atlas {
    pub fn compare_release(&self, query_id: &str) -> Result<ReleaseComparison<'_>, String> {
        let index = self.candidate_index(query_id)?;
        let current = &self.catalogue.observations[index];
        let release = &self.historical;
        let earlier = release
            .matches
            .get(&current.koi_id)
            .filter(|row| row.host_id == current.host_id)
            .ok_or_else(|| {
                format!(
                    "No matched DR24 observation with all eight usable measurements for {}.",
                    current.koi_id,
                )
            })?;

        let earlier_vector = Self::scale(&self.catalogue.features, &earlier.values);
        let current_vector = &self.scaled[index];
        let earlier_position = self.catalogue.projection.project(&earlier_vector);
        let current_position = self.catalogue.projection.project(current_vector);
        let standardised_deltas: Vector =
            std::array::from_fn(|i| current_vector[i] - earlier_vector[i]);
        let standardised_shift = standardised_deltas
            .iter()
            .map(|delta| delta * delta)
            .sum::<f64>()
            .sqrt();
        let projected_shift = current_position
            .into_iter()
            .zip(earlier_position)
            .map(|(a, b)| (a - b).powi(2))
            .sum::<f64>()
            .sqrt();

        let (eligible, _) = self.eligible_references(current.host_id);
        let earlier_neighbours = self.nearest(&earlier_vector, &eligible)?;
        let current_neighbours = self.nearest(current_vector, &eligible)?;
        let earlier_nearest = earlier_neighbours[0].observation.koi_id.as_str();
        let current_nearest = current_neighbours[0].observation.koi_id.as_str();
        let retained_neighbours = earlier_neighbours
            .iter()
            .filter(|earlier| {
                current_neighbours
                    .iter()
                    .any(|current| earlier.observation.koi_id == current.observation.koi_id)
            })
            .count();

        Ok(ReleaseComparison {
            release: &release.release,
            release_last_updated: &release.release_last_updated,
            retrieved_utc_date: &release.retrieved_utc_date,
            source_sha256: &release.source_sha256,
            earlier_query: Observation {
                koi_id: current.koi_id.clone(),
                host_id: earlier.host_id,
                disposition: earlier.disposition,
                values: earlier.values,
                position: earlier_position,
            },
            earlier_neighbours,
            standardised_shift,
            projected_shift,
            standardised_deltas,
            earlier_nearest,
            current_nearest,
            retained_neighbours,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reports_the_fixed_model_change_for_a_real_candidate() {
        let atlas = Atlas::load().unwrap();
        let result = atlas.compare_release("k00005.01").unwrap();
        assert_eq!(result.earlier_query.values[5], 5753.0);
        assert_eq!(result.earlier_nearest, "K00356.01");
        assert_eq!(result.current_nearest, "K01090.01");
        assert_eq!(result.retained_neighbours, 2);
        assert!(result.projected_shift <= result.standardised_shift + 1e-12);
        assert!((result.standardised_shift - 0.2324).abs() < 0.0001);
        assert!(result
            .earlier_neighbours
            .iter()
            .all(|row| row.observation.host_id != result.earlier_query.host_id));
    }

    #[test]
    fn explicitly_reports_missing_comparable_measurements() {
        let atlas = Atlas::load().unwrap();
        assert!(atlas
            .compare_release("K00115.03")
            .err()
            .unwrap()
            .contains("No matched DR24"));
    }
}
