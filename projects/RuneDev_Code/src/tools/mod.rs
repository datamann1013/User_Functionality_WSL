pub mod filesystem;
pub mod git;
pub mod search;
pub mod shell;

use serde_json::Value;
use std::path::PathBuf;

/// A tool definition in MCP JSON-schema format.
pub struct ToolDef {
    pub name: &'static str,
    pub description: &'static str,
    pub input_schema: Value,
}

/// All available tools, in MCP JSON-schema format.
pub fn all_tools() -> Vec<ToolDef> {
    vec![
        filesystem::read_file_def(),
        filesystem::write_file_def(),
        filesystem::create_file_def(),
        filesystem::delete_file_def(),
        filesystem::list_directory_def(),
        shell::run_bash_def(),
        search::search_files_def(),
        search::search_in_files_def(),
        git::git_status_def(),
        git::git_diff_def(),
        git::git_log_def(),
    ]
}

/// Convert a ToolDef to MCP-compatible JSON (for sending to the LLM or MCP clients).
pub fn tool_to_json(tool: &ToolDef) -> Value {
    serde_json::json!({
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.input_schema.clone()
    })
}

/// Execute a tool by name. Returns `(output, is_error)`.
pub async fn execute(name: &str, args: Value, cwd: &PathBuf) -> (String, bool) {
    match name {
        "read_file" => filesystem::read_file(args, cwd).await,
        "write_file" => filesystem::write_file(args, cwd).await,
        "create_file" => filesystem::create_file(args, cwd).await,
        "delete_file" => filesystem::delete_file(args, cwd).await,
        "list_directory" => filesystem::list_directory(args, cwd).await,
        "run_bash" => shell::run_bash(args, cwd).await,
        "search_files" => search::search_files(args, cwd).await,
        "search_in_files" => search::search_in_files(args, cwd).await,
        "git_status" => git::git_status(args, cwd).await,
        "git_diff" => git::git_diff(args, cwd).await,
        "git_log" => git::git_log(args, cwd).await,
        _ => (format!("Unknown tool: {}", name), true),
    }
}
