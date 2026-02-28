use clap::Parser;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(
    name = "runecode",
    about = "RuneDev_Code — native coding agent powered by local Ollama models",
    version
)]
pub struct Cli {
    /// Task to perform (one-shot mode). If omitted, enters interactive mode.
    pub task: Option<String>,

    /// Model override (e.g. qwen2.5-coder:14b)
    #[arg(long, short = 'm')]
    pub model: Option<String>,

    /// Skip all approval gates — execute every tool without asking
    #[arg(long)]
    pub auto: bool,

    /// Approve every action interactively regardless of config (safe audit mode)
    #[arg(long)]
    pub safe: bool,

    /// Disable CoreMemory session memory
    #[arg(long)]
    pub no_memory: bool,

    /// Run as MCP stdio server (exposes built-in tools to any MCP client)
    #[arg(long)]
    pub mcp_server: bool,

    /// Clean up runecode's own runtime files: ~/.config/runecode/ and
    /// the local .runecode.toml in the current project (if present).
    /// Does NOT touch the binary or source — use manage.sh -d for that.
    #[arg(long)]
    pub delete: bool,

    /// Working directory (defaults to current directory)
    #[arg(long, short = 'C')]
    pub dir: Option<PathBuf>,
}
