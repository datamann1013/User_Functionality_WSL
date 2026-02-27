mod agent;
mod approval;
mod cli;
mod config;
mod context;
mod display;
mod mcp_client;
mod mcp_server;
mod ollama;
mod tools;

use clap::Parser;
use cli::Cli;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    if cli.mcp_server {
        mcp_server::run().await
    } else {
        agent::run(cli).await
    }
}
