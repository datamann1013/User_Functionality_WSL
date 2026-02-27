use serde_json::Value;

use crate::config::ApprovalConfig;
use crate::display;

pub struct ApprovalGate {
    config: ApprovalConfig,
    /// True when the user chose 'a' (allow all for this session) or --auto flag was set.
    allow_all: bool,
    /// True when --safe flag: always prompt regardless of config.
    always_ask: bool,
}

impl ApprovalGate {
    pub fn new(config: ApprovalConfig, auto_mode: bool, always_ask: bool) -> Self {
        ApprovalGate {
            config,
            allow_all: auto_mode,
            always_ask,
        }
    }

    /// Check whether `tool_name` is allowed to run.
    /// Prints approval prompt if needed. Returns `true` = proceed.
    pub fn check(&mut self, tool_name: &str, args_display: &str) -> bool {
        // --auto flag: run everything silently
        if self.allow_all {
            return true;
        }

        // --safe: always prompt
        if !self.always_ask && self.config.auto_allow.iter().any(|t| t == tool_name) {
            // Auto-allowed — silent
            return true;
        }

        // Ask the user
        let ch = display::approval_prompt(tool_name, args_display);
        match ch {
            'y' => true,
            'a' => {
                self.allow_all = true;
                true
            }
            'q' => {
                println!("\nAborted.");
                std::process::exit(0);
            }
            _ => false,
        }
    }

    /// True if this tool runs silently (no prompt printed before execution).
    pub fn is_auto(&self, tool_name: &str) -> bool {
        self.allow_all
            || (!self.always_ask && self.config.auto_allow.iter().any(|t| t == tool_name))
    }

    /// Truncate & format args Value for single-line display.
    pub fn format_args(args: &Value) -> String {
        let s = serde_json::to_string(args).unwrap_or_default();
        if s.len() > 120 {
            format!("{}…", &s[..120])
        } else {
            s
        }
    }
}
