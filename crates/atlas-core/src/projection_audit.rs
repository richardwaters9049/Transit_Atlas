use std::cmp::Ordering;

use serde::Serialize;

use crate::{squared_deltas, Atlas, Disposition, K};

#[derive(Debug, Serialize)]
pub struct ProjectionAudit<'a> {
    pub candidates: Vec<CandidateAudit<'a>>,
    pub by_overlap: [usize; K + 1],
    pub changed_nearest: usize,
}

#[derive(Debug, Serialize)]
pub struct CandidateAudit<'a> {
    koi_id: &'a str,
    eligible_references: usize,
    shared: usize,
    projected_neighbours: [ProjectedNeighbour<'a>; K],
}

#[derive(Debug, Serialize)]
struct ProjectedNeighbour<'a> {
    koi_id: &'a str,
    position: [f64; 3],
    full_rank: usize,
    projected_distance: f64,
    full_distance: f64,
    omitted_share: Option<f64>,
}

#[derive(Clone, Copy)]
struct Distances {
    index: usize,
    projected_squared: f64,
    full_squared: f64,
}

impl Atlas {
    pub fn projection_audit(&self) -> Result<ProjectionAudit<'_>, String> {
        let observations = &self.catalogue.observations;
        let mut candidates = Vec::new();
        let mut by_overlap = [0; K + 1];
        let mut changed_nearest = 0;
        for (index, row) in observations.iter().enumerate() {
            if row.disposition != Disposition::Candidate {
                continue;
            }
            let audit = self.audit_candidate(index)?;
            by_overlap[audit.shared] += 1;
            changed_nearest += usize::from(audit.projected_neighbours[0].full_rank != 1);
            candidates.push(audit);
        }
        Ok(ProjectionAudit {
            candidates,
            by_overlap,
            changed_nearest,
        })
    }

    fn audit_candidate(&self, query_index: usize) -> Result<CandidateAudit<'_>, String> {
        let observations = &self.catalogue.observations;
        let query = &observations[query_index];
        let (eligible, _) = self.eligible_references(query.host_id);
        if eligible.len() < K {
            return Err(format!(
                "Only {} eligible reference signals",
                eligible.len()
            ));
        }
        let mut distances: Vec<_> = eligible
            .into_iter()
            .map(|index| Distances {
                index,
                projected_squared: squared_deltas(&observations[index].position, &query.position)
                    .into_iter()
                    .sum(),
                full_squared: squared_deltas(&self.scaled[index], &self.scaled[query_index])
                    .into_iter()
                    .sum(),
            })
            .collect();
        // Observation indices follow lexicographic KOI order.
        let by_projection = |left: &Distances, right: &Distances| {
            left.projected_squared
                .total_cmp(&right.projected_squared)
                .then_with(|| left.index.cmp(&right.index))
        };
        distances.select_nth_unstable_by(K - 1, by_projection);
        distances[..K].sort_unstable_by(by_projection);

        let projected_neighbours = std::array::from_fn(|rank| {
            let reference = &distances[rank];
            let full_rank = 1 + distances
                .iter()
                .filter(|other| {
                    other
                        .full_squared
                        .total_cmp(&reference.full_squared)
                        .then_with(|| other.index.cmp(&reference.index))
                        == Ordering::Less
                })
                .count();
            let omitted_share = (reference.full_squared > 0.0).then(|| {
                // Clamp small floating-point errors at the endpoints.
                (1.0 - reference.projected_squared / reference.full_squared).clamp(0.0, 1.0)
            });
            ProjectedNeighbour {
                koi_id: &observations[reference.index].koi_id,
                position: observations[reference.index].position,
                full_rank,
                projected_distance: reference.projected_squared.sqrt(),
                full_distance: reference.full_squared.sqrt(),
                omitted_share,
            }
        });
        let shared = projected_neighbours
            .iter()
            .filter(|reference| reference.full_rank <= K)
            .count();
        Ok(CandidateAudit {
            koi_id: &query.koi_id,
            eligible_references: distances.len(),
            shared,
            projected_neighbours,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn catalogue_audit_matches_independent_numpy_calculation() {
        let atlas = Atlas::load().unwrap();
        let audit = atlas.projection_audit().unwrap();
        assert_eq!(audit.candidates.len(), 1872);
        assert_eq!(audit.by_overlap, [601, 667, 406, 150, 42, 6]);
        assert_eq!(audit.changed_nearest, 1642);

        let candidate = audit
            .candidates
            .iter()
            .find(|row| row.koi_id == "K00115.03")
            .unwrap();
        assert_eq!(candidate.eligible_references, 5781);
        assert_eq!(candidate.shared, 0);
        assert_eq!(
            candidate
                .projected_neighbours
                .each_ref()
                .map(|row| row.full_rank),
            [1836, 279, 26, 38, 15]
        );
        let closest = &candidate.projected_neighbours[0];
        assert_eq!(closest.koi_id, "K08264.01");
        assert!((closest.projected_distance - 0.16225846535404556).abs() < 1e-12);
        assert!((closest.full_distance - 2.014583157525694).abs() < 1e-12);
        assert!((closest.omitted_share.unwrap() - 0.9935129935378025).abs() < 1e-12);
    }
}
