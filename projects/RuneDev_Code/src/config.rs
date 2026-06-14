use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct ModelConfig {
    pub name: String,
    pub wrapper_url: String,
    pub temperature: f64,
}

impl Default for ModelConfig {
    fn default() -> Self {
        ModelConfig {
            name: "qwen2.5-coder:7b".to_string(),
            wrapper_url: "http://localhost:5002".to_string(),
            temperature: 0.2,
        }
    }
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct ApprovalConfig {
    /// Tools executed without asking
    pub auto_allow: Vec<String>,
    /// Tools that always prompt for approval
    pub always_approve: Vec<String>,
}

impl Default for ApprovalConfig {
    fn default() -> Self {
        ApprovalConfig {
            auto_allow: vec![
                "read_file".to_string(),
                "list_directory".to_string(),
                "search_files".to_string(),
                "search_in_files".to_string(),
                "git_status".to_string(),
                "git_diff".to_string(),
                "git_log".to_string(),
            ],
            always_approve: vec![
                "write_file".to_string(),
                "create_file".to_string(),
                "delete_file".to_string(),
                "run_bash".to_string(),
                "git_commit".to_string(),
            ],
        }
    }
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct ContextConfig {
    pub max_file_size_kb: u64,
    pub project_context_files: Vec<String>,
    pub respect_gitignore: bool,
}

impl Default for ContextConfig {
    fn default() -> Self {
        ContextConfig {
            max_file_size_kb: 16,
            project_context_files: vec![
                "README.md".to_string(),
                "CLAUDE.md".to_string(),
                "Cargo.toml".to_string(),
                "package.json".to_string(),
                "pyproject.toml".to_string(),
                ".runecode.toml".to_string(),
            ],
            respect_gitignore: true,
        }
    }
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct RuneCoreConfig {
    pub register: bool,
    pub core_url: String,
}

impl Default for RuneCoreConfig {
    fn default() -> Self {
        RuneCoreConfig {
            register: true,
            core_url: "https://localhost:11440".to_string(),
        }
    }
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct SecurityConfig {
    /// Sandbox root for filesystem tools. Empty = project root (cwd).
    #[serde(default)]
    pub sandbox_root: String,
    /// Allow filesystem tools to touch paths outside the sandbox root.
    #[serde(default)]
    pub allow_outside_root: bool,
    /// Extra regex patterns for `run_bash`, merged with the builtin denylist.
    #[serde(default)]
    pub shell_denylist: Vec<String>,
    /// If non-empty, `run_bash` commands must match one of these regexes.
    #[serde(default)]
    pub shell_allowlist: Vec<String>,
}

impl Default for SecurityConfig {
    fn default() -> Self {
        SecurityConfig {
            sandbox_root: String::new(),
            allow_outside_root: false,
            shell_denylist: Vec::new(),
            shell_allowlist: Vec::new(),
        }
    }
}

/// An external MCP server runecode can connect to as a client.
/// These servers are spawned as subprocesses and communicate via stdio.
///
/// Example (.runecode.toml):
///   [[mcp_servers]]
///   name = "playwright"
///   command = "npx"
///   args = ["-y", "@playwright/mcp"]
#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct McpServerConfig {
    pub name: String,
    pub command: String,
    #[serde(default)]
    pub args: Vec<String>,
}

#[derive(Debug, Deserialize, Serialize, Clone, Default)]
pub struct Config {
    #[serde(default)]
    pub model: ModelConfig,
    #[serde(default)]
    pub approval: ApprovalConfig,
    #[serde(default)]
    pub context: ContextConfig,
    #[serde(default)]
    pub runecore: RuneCoreConfig,
    #[serde(default)]
    pub security: SecurityConfig,
    /// External MCP servers to connect to as a client
    #[serde(default)]
    pub mcp_servers: Vec<McpServerConfig>,
}

impl Config {
    /// Load config: project-level `.runecode.toml` → global `~/.config/runecode/config.toml` → defaults
    pub fn load(project_root: &Path) -> Self {
        Self::try_load(project_root).unwrap_or_default()
    }

    fn try_load(project_root: &Path) -> Result<Self> {
        let project_cfg = project_root.join(".runecode.toml");
        if project_cfg.exists() {
            let content = std::fs::read_to_string(&project_cfg)?;
            return Ok(toml::from_str(&content)?);
        }

        if let Some(cfg_dir) = dirs::config_dir() {
            let global_cfg = cfg_dir.join("runecode").join("config.toml");
            if global_cfg.exists() {
                let content = std::fs::read_to_string(&global_cfg)?;
                return Ok(toml::from_str(&content)?);
            }
        }

        Ok(Config::default())
    }

    pub fn global_config_dir() -> Option<PathBuf> {
        dirs::config_dir().map(|d| d.join("runecode"))
    }
}
