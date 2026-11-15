use atlas_core::Atlas;
use serde_json::Value;
use tauri::{Manager, State};

mod study_files;

#[tauri::command]
fn catalogue(state: State<'_, Atlas>) -> Result<Value, String> {
    serde_json::to_value(state.catalogue()).map_err(|error| error.to_string())
}

#[tauri::command]
fn neighbours(query_id: String, state: State<'_, Atlas>) -> Result<Value, String> {
    serde_json::to_value(state.lookup(&query_id)?).map_err(|error| error.to_string())
}

#[tauri::command]
fn exact_sensitivity(query_id: String, state: State<'_, Atlas>) -> Result<Value, String> {
    let report = state.exact_sensitivity(&query_id)?;
    if std::env::var("TRANSIT_ATLAS_TRACE").as_deref() == Ok("1") {
        println!(
            "[Transit Atlas] {} · exact bounds · {:?} · {} → {} · gap {:.6}",
            report.query,
            report.status,
            report.nominal_nearest,
            report
                .witness
                .as_ref()
                .map_or(report.nominal_nearest, |witness| witness.nearest()),
            report.minimum_gap,
        );
    }
    serde_json::to_value(report).map_err(|error| error.to_string())
}

#[tauri::command]
async fn projection_audit(app: tauri::AppHandle) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let atlas = app.state::<Atlas>();
        let audit = atlas.projection_audit()?;
        if std::env::var("TRANSIT_ATLAS_TRACE").as_deref() == Ok("1") {
            println!(
                "[Transit Atlas] Projection audit · {} candidates · {} with no shared top five · {} with a different nearest neighbour",
                audit.candidates.len(), audit.by_overlap[0], audit.changed_nearest,
            );
        }
        serde_json::to_value(audit).map_err(|error| error.to_string())
    })
    .await
    .map_err(|error| error.to_string())?
}

#[tauri::command]
fn compare_release(query_id: String, state: State<'_, Atlas>) -> Result<Value, String> {
    let result = state.compare_release(&query_id)?;
    if std::env::var("TRANSIT_ATLAS_TRACE").as_deref() == Ok("1") {
        println!(
            "[Transit Atlas] {query_id} · DR24 {} → cumulative {} · {}/5 shared · 8D shift {:.4}",
            result.earlier_nearest,
            result.current_nearest,
            result.retained_neighbours,
            result.standardised_shift,
        );
    }
    serde_json::to_value(result).map_err(|error| error.to_string())
}

#[tauri::command]
async fn stability(query_id: String, state: State<'_, Atlas>) -> Result<Value, String> {
    let report = state.stability(&query_id)?;
    if std::env::var("TRANSIT_ATLAS_TRACE").as_deref() == Ok("1") {
        println!(
            "[Transit Atlas] {} · {} scenarios × {} references · same nearest {}/{} · same top five {}/{}",
            report.query, report.trials, report.eligible_references,
            report.same_first, report.trials, report.same_top_five, report.trials,
        );
    }
    serde_json::to_value(report).map_err(|error| error.to_string())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            app.manage(Atlas::load()?);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            catalogue,
            neighbours,
            exact_sensitivity,
            projection_audit,
            stability,
            compare_release,
            study_files::save_study,
            study_files::open_study
        ])
        .run(tauri::generate_context!())
        .expect("could not start Transit Atlas");
}
