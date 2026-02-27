use std::path::PathBuf;

use super::ToolDef;

pub fn search_files_def() -> ToolDef {
    ToolDef {
        name: "search_files",
        description: "Find files matching a glob pattern (e.g. '**/*.rs')",
        input_schema: serde_json::json!({
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern relative to base_dir"
                },
                "base_dir": {
                    "type": "string",
                    "description": "Base directory for the search (defaults to project root)"
                }
            },
            "required": ["pattern"]
        }),
    }
}

pub fn search_in_files_def() -> ToolDef {
    ToolDef {
        name: "search_in_files",
        description: "Search for a regex pattern inside files matching a glob",
        input_schema: serde_json::json!({
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for"
                },
                "file_glob": {
                    "type": "string",
                    "description": "Glob pattern for files to search (default: '**/*')"
                },
                "base_dir": {
                    "type": "string",
                    "description": "Base directory (defaults to project root)"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of matching lines to return (default: 50)"
                }
            },
            "required": ["pattern"]
        }),
    }
}

pub async fn search_files(args: serde_json::Value, cwd: &PathBuf) -> (String, bool) {
    let pattern = match args.get("pattern").and_then(|v| v.as_str()) {
        Some(p) => p.to_string(),
        None => return ("Missing required argument: pattern".to_string(), true),
    };

    let base = match args.get("base_dir").and_then(|v| v.as_str()) {
        Some(b) => {
            let p = PathBuf::from(b);
            if p.is_absolute() { p } else { cwd.join(p) }
        }
        None => cwd.clone(),
    };

    let full_pattern = format!("{}/{pattern}", base.to_string_lossy());

    match glob::glob(&full_pattern) {
        Ok(paths) => {
            let mut results: Vec<String> = paths
                .filter_map(|p| p.ok())
                .map(|p| p.to_string_lossy().to_string())
                .collect();
            results.sort();
            if results.is_empty() {
                ("No files matched".to_string(), false)
            } else {
                (results.join("\n"), false)
            }
        }
        Err(e) => (format!("Invalid glob pattern: {e}"), true),
    }
}

pub async fn search_in_files(args: serde_json::Value, cwd: &PathBuf) -> (String, bool) {
    use regex::Regex;

    let pattern_str = match args.get("pattern").and_then(|v| v.as_str()) {
        Some(p) => p.to_string(),
        None => return ("Missing required argument: pattern".to_string(), true),
    };

    let file_glob = args
        .get("file_glob")
        .and_then(|v| v.as_str())
        .unwrap_or("**/*")
        .to_string();

    let max_results = args
        .get("max_results")
        .and_then(|v| v.as_u64())
        .unwrap_or(50) as usize;

    let base = match args.get("base_dir").and_then(|v| v.as_str()) {
        Some(b) => {
            let p = PathBuf::from(b);
            if p.is_absolute() { p } else { cwd.join(b) }
        }
        None => cwd.clone(),
    };

    let re = match Regex::new(&pattern_str) {
        Ok(r) => r,
        Err(e) => return (format!("Invalid regex: {e}"), true),
    };

    let full_glob = format!("{}/{file_glob}", base.to_string_lossy());
    let paths: Vec<PathBuf> = match glob::glob(&full_glob) {
        Ok(p) => p.filter_map(|e| e.ok()).collect(),
        Err(e) => return (format!("Invalid file glob: {e}"), true),
    };

    let mut results: Vec<String> = Vec::new();

    'outer: for path in &paths {
        if path.is_dir() {
            continue;
        }
        let content = match std::fs::read_to_string(path) {
            Ok(c) => c,
            Err(_) => continue, // skip binary or unreadable files
        };

        for (line_num, line) in content.lines().enumerate() {
            if re.is_match(line) {
                results.push(format!(
                    "{}:{}: {}",
                    path.to_string_lossy(),
                    line_num + 1,
                    line.trim()
                ));
                if results.len() >= max_results {
                    break 'outer;
                }
            }
        }
    }

    if results.is_empty() {
        ("No matches found".to_string(), false)
    } else {
        (results.join("\n"), false)
    }
}
