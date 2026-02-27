use std::path::PathBuf;

use super::ToolDef;

pub fn read_file_def() -> ToolDef {
    ToolDef {
        name: "read_file",
        description: "Read the full contents of a file",
        input_schema: serde_json::json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path (relative to project root or absolute)"
                }
            },
            "required": ["path"]
        }),
    }
}

pub fn write_file_def() -> ToolDef {
    ToolDef {
        name: "write_file",
        description: "Overwrite a file completely with new content",
        input_schema: serde_json::json!({
            "type": "object",
            "properties": {
                "path": { "type": "string", "description": "File path" },
                "content": { "type": "string", "description": "New file content" }
            },
            "required": ["path", "content"]
        }),
    }
}

pub fn create_file_def() -> ToolDef {
    ToolDef {
        name: "create_file",
        description: "Create a new file with the given content (fails if file already exists)",
        input_schema: serde_json::json!({
            "type": "object",
            "properties": {
                "path": { "type": "string", "description": "File path" },
                "content": { "type": "string", "description": "File content" }
            },
            "required": ["path", "content"]
        }),
    }
}

pub fn delete_file_def() -> ToolDef {
    ToolDef {
        name: "delete_file",
        description: "Delete a file permanently",
        input_schema: serde_json::json!({
            "type": "object",
            "properties": {
                "path": { "type": "string", "description": "File path to delete" }
            },
            "required": ["path"]
        }),
    }
}

pub fn list_directory_def() -> ToolDef {
    ToolDef {
        name: "list_directory",
        description: "List files and subdirectories at a path (one entry per line)",
        input_schema: serde_json::json!({
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path (defaults to project root if omitted)"
                }
            },
            "required": []
        }),
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn resolve(args: &serde_json::Value, key: &str, cwd: &PathBuf) -> Option<PathBuf> {
    let s = args.get(key)?.as_str()?;
    let p = PathBuf::from(s);
    if p.is_absolute() {
        Some(p)
    } else {
        Some(cwd.join(p))
    }
}

// ---------------------------------------------------------------------------
// Executors
// ---------------------------------------------------------------------------

pub async fn read_file(args: serde_json::Value, cwd: &PathBuf) -> (String, bool) {
    let path = match resolve(&args, "path", cwd) {
        Some(p) => p,
        None => return ("Missing required argument: path".to_string(), true),
    };

    match std::fs::read_to_string(&path) {
        Ok(content) => {
            let line_count = content.lines().count();
            (
                format!("```\n{content}\n```\n({line_count} lines)"),
                false,
            )
        }
        Err(e) => (format!("Error reading {}: {e}", path.display()), true),
    }
}

pub async fn write_file(args: serde_json::Value, cwd: &PathBuf) -> (String, bool) {
    let path = match resolve(&args, "path", cwd) {
        Some(p) => p,
        None => return ("Missing required argument: path".to_string(), true),
    };
    let content = match args.get("content").and_then(|v| v.as_str()) {
        Some(c) => c.to_string(),
        None => return ("Missing required argument: content".to_string(), true),
    };

    if let Some(parent) = path.parent() {
        if let Err(e) = std::fs::create_dir_all(parent) {
            return (format!("Failed to create parent directories: {e}"), true);
        }
    }

    match std::fs::write(&path, &content) {
        Ok(_) => (
            format!("Written {} bytes to {}", content.len(), path.display()),
            false,
        ),
        Err(e) => (format!("Error writing {}: {e}", path.display()), true),
    }
}

pub async fn create_file(args: serde_json::Value, cwd: &PathBuf) -> (String, bool) {
    let path = match resolve(&args, "path", cwd) {
        Some(p) => p,
        None => return ("Missing required argument: path".to_string(), true),
    };

    if path.exists() {
        return (
            format!("File already exists: {} — use write_file to overwrite", path.display()),
            true,
        );
    }

    let content = match args.get("content").and_then(|v| v.as_str()) {
        Some(c) => c.to_string(),
        None => return ("Missing required argument: content".to_string(), true),
    };

    if let Some(parent) = path.parent() {
        if let Err(e) = std::fs::create_dir_all(parent) {
            return (format!("Failed to create parent directories: {e}"), true);
        }
    }

    match std::fs::write(&path, &content) {
        Ok(_) => (
            format!("Created {} ({} bytes)", path.display(), content.len()),
            false,
        ),
        Err(e) => (format!("Error creating {}: {e}", path.display()), true),
    }
}

pub async fn delete_file(args: serde_json::Value, cwd: &PathBuf) -> (String, bool) {
    let path = match resolve(&args, "path", cwd) {
        Some(p) => p,
        None => return ("Missing required argument: path".to_string(), true),
    };

    if !path.exists() {
        return (format!("File not found: {}", path.display()), true);
    }

    match std::fs::remove_file(&path) {
        Ok(_) => (format!("Deleted {}", path.display()), false),
        Err(e) => (format!("Error deleting {}: {e}", path.display()), true),
    }
}

pub async fn list_directory(args: serde_json::Value, cwd: &PathBuf) -> (String, bool) {
    let dir = match args.get("path").and_then(|v| v.as_str()) {
        Some(s) => {
            let p = PathBuf::from(s);
            if p.is_absolute() { p } else { cwd.join(p) }
        }
        None => cwd.clone(),
    };

    match std::fs::read_dir(&dir) {
        Ok(entries) => {
            let mut items: Vec<String> = entries
                .filter_map(|e| e.ok())
                .map(|e| {
                    let name = e.file_name().to_string_lossy().to_string();
                    let is_dir = e.file_type().map(|ft| ft.is_dir()).unwrap_or(false);
                    if is_dir { format!("{name}/") } else { name }
                })
                .collect();
            items.sort();
            if items.is_empty() {
                ("(empty directory)".to_string(), false)
            } else {
                (items.join("\n"), false)
            }
        }
        Err(e) => (format!("Error listing {}: {e}", dir.display()), true),
    }
}
