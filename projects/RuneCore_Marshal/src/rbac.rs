use crate::config::MarshalConfig;

/// RBAC check result
#[derive(Debug)]
pub enum RbacResult {
    /// Caller is authorized for this action
    Allowed,
    /// Caller is known but not authorized for this action
    Denied { caller_cn: String, action: String },
    /// No role found for this CN
    UnknownCaller { cn: String },
}

/// Check whether the caller identified by `caller_cn` is allowed to perform `action`.
///
/// Action matching supports simple wildcard suffix: "service.*" matches "service.status" etc.
pub fn check(cfg: &MarshalConfig, caller_cn: &str, action: &str) -> RbacResult {
    let role = cfg.roles.iter().find(|r| r.caller_cn == caller_cn);

    match role {
        None => RbacResult::UnknownCaller {
            cn: caller_cn.to_string(),
        },
        Some(r) => {
            let allowed = r.allowed_actions.iter().any(|a| {
                if a.ends_with(".*") {
                    // Wildcard: "service.*" matches "service.status", "service.stop", etc.
                    let prefix = &a[..a.len() - 1]; // "service."
                    action.starts_with(prefix)
                } else {
                    a == action
                }
            });

            if allowed {
                RbacResult::Allowed
            } else {
                RbacResult::Denied {
                    caller_cn: caller_cn.to_string(),
                    action: action.to_string(),
                }
            }
        }
    }
}

/// Convenience: returns the caller CN from a possibly-None value,
/// returning an error string if CN could not be determined.
pub fn require_caller_cn(cn: Option<&str>) -> Result<&str, &'static str> {
    cn.ok_or("No client certificate presented — mTLS required")
}
