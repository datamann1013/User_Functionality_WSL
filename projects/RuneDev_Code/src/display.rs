use std::io::{self, Write};

use colored::Colorize;

pub fn print_header(model: &str, project_root: &str) {
    let sep = "─".repeat(60);
    println!("{}", sep.dimmed());
    println!("  {} RuneDev_Code  {}", "◆".blue().bold(), model.cyan());
    println!("  {} {}", "⌂".dimmed(), project_root.dimmed());
    println!("{}", sep.dimmed());
}

pub fn print_separator() {
    println!("{}", "─".repeat(60).dimmed());
}

/// Print the interactive input prompt.
pub fn print_prompt() {
    print!("\n{} ", "▶".blue().bold());
    let _ = io::stdout().flush();
}

/// Show a "thinking..." spinner line (overwritten by clear_thinking).
pub fn print_thinking() {
    print!("\n  {}", "◦ thinking...".dimmed());
    let _ = io::stdout().flush();
}

/// Erase the thinking line.
pub fn clear_thinking() {
    // Move to start of line, overwrite with spaces, return to start
    print!("\r{}\r", " ".repeat(30));
    let _ = io::stdout().flush();
}

/// Print a text chunk directly to stdout (no newline) — used for streamed output.
pub fn print_chunk(text: &str) {
    print!("{text}");
    let _ = io::stdout().flush();
}

pub fn print_newline() {
    println!();
}

/// Auto-approved tool being executed (dim, no prompt).
pub fn print_tool_exec(name: &str, args_preview: &str) {
    println!("  {}  {}  {}", "⚙".dimmed(), name.dimmed(), args_preview.dimmed());
}

/// Tool result after execution.
pub fn print_tool_result(name: &str, preview: &str, is_error: bool) {
    if is_error {
        println!("  {}  {}  {}", "✗".red(), name, preview.red());
    } else {
        println!("  {}  {}  {}", "✓".green(), name, preview.dimmed());
    }
}

/// Tool call was denied by the user.
pub fn print_tool_denied(name: &str) {
    println!("  {}  {}  {}", "✗".red(), name, "denied".red());
}

/// Show the approval prompt (returns the user's choice character).
pub fn approval_prompt(name: &str, args_display: &str) -> char {
    println!();
    println!("  {}  {}  {}", "►".yellow(), name.bold(), args_display);
    print!("  Allow? [y/n/a/q] ");
    let _ = io::stdout().flush();

    let mut input = String::new();
    if io::stdin().read_line(&mut input).is_err() {
        return 'n';
    }
    input.trim().chars().next().unwrap_or('n').to_ascii_lowercase()
}
