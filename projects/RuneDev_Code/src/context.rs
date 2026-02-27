use std::path::{Path, PathBuf};

use crate::config::Config;

pub struct ProjectContext {
    pub root: PathBuf,
    pub system_prompt: String,
}

/// Build project context and system prompt from the working directory.
pub fn build(cwd: &Path, config: &Config) -> ProjectContext {
    let root = find_git_root(cwd).unwrap_or_else(|| cwd.to_path_buf());

    let mut parts: Vec<String> = vec![
        concat!(
            "You are RuneDev_Code, an expert coding assistant running directly on the user's machine.\n",
            "You have access to tools to read files, write files, run shell commands, and query git.\n",
            "Be precise and efficient. Always read files before modifying them.\n",
            "Think step by step. When making changes, show what you're doing."
        ).to_string(),
        format!("Project root: {}", root.display()),
    ];

    // Detect language/build system from key files
    let mut detected = vec![];
    if root.join("Cargo.toml").exists() { detected.push("Rust (Cargo)"); }
    if root.join("package.json").exists() { detected.push("JavaScript/TypeScript (npm/node)"); }
    if root.join("pyproject.toml").exists() || root.join("setup.py").exists() { detected.push("Python"); }
    if root.join("go.mod").exists() { detected.push("Go"); }
    if !detected.is_empty() {
        parts.push(format!("Detected: {}", detected.join(", ")));
    }

    // Read key project files for context
    let max_bytes = (config.context.max_file_size_kb * 1024) as usize;
    for filename in &config.context.project_context_files {
        let path = root.join(filename);
        if path.exists() {
            if let Ok(content) = std::fs::read_to_string(&path) {
                let body = if content.len() > max_bytes {
                    format!("{}\n[...truncated]", &content[..max_bytes])
                } else {
                    content
                };
                parts.push(format!("--- {} ---\n{}", filename, body));
            }
        }
    }

    if config.context.respect_gitignore {
        parts.push(
            "Respect .gitignore patterns when listing or searching files.".to_string(),
        );
    }

    ProjectContext {
        root,
        system_prompt: parts.join("\n\n"),
    }
}

fn find_git_root(path: &Path) -> Option<PathBuf> {
    let mut current = path.to_path_buf();
    loop {
        if current.join(".git").exists() {
            return Some(current);
        }
        if !current.pop() {
            return None;
        }
    }
}
