use std::fs::File;
use std::io::{Read, Write};
use std::path::Path;

use tauri::AppHandle;
use tauri_plugin_dialog::DialogExt;

const MAX_STUDY_BYTES: usize = 256 * 1024;

fn validated_candidate(document: &str) -> Result<String, String> {
    if document.len() > MAX_STUDY_BYTES {
        return Err("Study files must be 256 KiB or smaller.".into());
    }
    let data: serde_json::Value = serde_json::from_str(document)
        .map_err(|_| "The selected file does not contain valid JSON.")?;
    if data["schema"].as_str() != Some("transit-atlas.study") || data["version"].as_u64() != Some(1)
    {
        return Err("This file uses an unsupported Transit Atlas study format.".into());
    }
    let candidate = data["selection"]["candidate"]
        .as_str()
        .filter(|id| match id.as_bytes() {
            [b'K', a, b, c, d, e, b'.', f, g] => [a, b, c, d, e, f, g]
                .iter()
                .all(|byte| byte.is_ascii_digit()),
            _ => false,
        })
        .ok_or("The study does not identify a valid Kepler candidate.")?;
    Ok(candidate.into())
}

fn write_study(path: &Path, document: &str) -> Result<(), String> {
    validated_candidate(document)?;
    let parent = path
        .parent()
        .ok_or("The selected file has no parent folder.")?;
    let mut temp = tempfile::NamedTempFile::new_in(parent).map_err(|error| error.to_string())?;
    temp.write_all(document.as_bytes())
        .map_err(|error| error.to_string())?;
    temp.as_file()
        .sync_all()
        .map_err(|error| error.to_string())?;
    temp.persist(path).map_err(|error| error.to_string())?;
    Ok(())
}

fn read_study(path: &Path) -> Result<String, String> {
    if !path
        .metadata()
        .map_err(|error| error.to_string())?
        .is_file()
    {
        return Err("Choose a regular JSON study file.".into());
    }
    let file = File::open(path).map_err(|error| error.to_string())?;
    let mut document = String::new();
    file.take(MAX_STUDY_BYTES as u64 + 1)
        .read_to_string(&mut document)
        .map_err(|error| error.to_string())?;
    validated_candidate(&document)?;
    Ok(document)
}

#[tauri::command]
pub async fn save_study(app: AppHandle, document: String) -> Result<Option<String>, String> {
    let candidate = validated_candidate(&document)?;
    tauri::async_runtime::spawn_blocking(move || {
        let Some(selected) = app
            .dialog()
            .file()
            .set_title("Save Transit Atlas study")
            .set_file_name(format!("{candidate}.atlas.json"))
            .add_filter("Transit Atlas study", &["json"])
            .blocking_save_file()
        else {
            return Ok(None);
        };
        let path = selected.into_path().map_err(|error| error.to_string())?;
        write_study(&path, &document)?;
        Ok(path
            .file_name()
            .map(|name| name.to_string_lossy().into_owned()))
    })
    .await
    .map_err(|error| error.to_string())?
}

#[tauri::command]
pub async fn open_study(app: AppHandle) -> Result<Option<String>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let Some(selected) = app
            .dialog()
            .file()
            .set_title("Open Transit Atlas study")
            .add_filter("Transit Atlas study", &["json"])
            .blocking_pick_file()
        else {
            return Ok(None);
        };
        let path = selected.into_path().map_err(|error| error.to_string())?;
        read_study(&path).map(Some)
    })
    .await
    .map_err(|error| error.to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;

    const DOCUMENT: &str =
        r#"{"schema":"transit-atlas.study","version":1,"selection":{"candidate":"K00005.01"}}"#;

    #[test]
    fn saves_and_reopens_a_local_document() {
        let folder = tempfile::tempdir().unwrap();
        let path = folder.path().join("K00005.01.atlas.json");
        write_study(&path, DOCUMENT).unwrap();
        assert_eq!(read_study(&path).unwrap(), DOCUMENT);
        assert!(write_study(&path, "{}").is_err());
        assert_eq!(read_study(&path).unwrap(), DOCUMENT);
    }

    #[test]
    fn rejects_incompatible_and_oversized_documents() {
        assert!(validated_candidate(&DOCUMENT.replace("\"version\":1", "\"version\":2")).is_err());
        assert!(validated_candidate(&DOCUMENT.replace("K00005.01", "../elsewhere")).is_err());
        let folder = tempfile::tempdir().unwrap();
        let path = folder.path().join("large.json");
        std::fs::write(&path, " ".repeat(MAX_STUDY_BYTES + 1)).unwrap();
        assert!(read_study(&path).unwrap_err().contains("256 KiB"));
    }
}
