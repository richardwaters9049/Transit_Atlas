use std::time::Instant;

use atlas_core::Atlas;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let atlas = Atlas::load()?;
    let queries: Vec<_> = std::env::args().skip(1).collect();
    for query in if queries.is_empty() {
        vec!["K00115.03".to_owned()]
    } else {
        queries
    } {
        println!("\n{query} · varying the candidate within its quoted measurement ranges");
        let start = Instant::now();
        let result = atlas.stability(&query)?;
        println!(
            "{} scenarios × {} eligible references × 8 measurements",
            result.trials, result.eligible_references,
        );
        println!("Quoted errors retrieved {}", result.source_date);
        for item in result.measurements {
            match item.bounds {
                Some([low, high]) => {
                    println!("  {:30} {:.8} to {:.8} {}", item.name, low, high, item.unit)
                }
                None => println!(
                    "  {:30} fixed at {} {}",
                    item.name, item.original, item.unit
                ),
            }
        }
        println!(
            "\n  Same nearest neighbour   {:>2}/{}",
            result.same_first, result.trials
        );
        println!(
            "  Same top-five membership {:>2}/{}",
            result.same_top_five, result.trials
        );
        for item in result.baseline {
            println!(
                "  {:>12} in the top five {:>2}/{} times",
                item.koi_id, item.appearances, result.trials
            );
        }
        if !result.replacements.is_empty() {
            println!(
                "  Most frequent replacements ({} distinct):",
                result.replacement_count
            );
            for item in result.replacements {
                println!(
                    "    {} · {}/{} scenarios",
                    item.koi_id, item.appearances, result.trials
                );
            }
        }
        println!(
            "  Computed in {:.2?}. Counts describe these scenarios.",
            start.elapsed()
        );
    }
    Ok(())
}
