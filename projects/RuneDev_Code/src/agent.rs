use std::io::{self, BufRead, Write};
use std::path::PathBuf;

use anyhow::Result;
use serde_json::Value;
use tokio::sync::broadcast;

use crate::approval::ApprovalGate;
use crate::cli::Cli;
use crate::config::Config;
use crate::context;
use crate::display;
use crate::mcp_client::{self, McpRegistry};
use crate::ollama::{AgentRequest, OllamaClient};
use crate::tools;

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

pub async fn run(cli: Cli) -> Result<()> {
    let cwd = cli
        .dir
        .clone()
        .unwrap_or_else(|| std::env::current_dir().expect("Cannot determine cwd"));

    // --delete: clean up runecode's own runtime files, then exit
    if cli.delete {
        return run_delete(&cwd).await;
    }

    let config = Config::load(&cwd);
    let model = cli.model.clone().unwrap_or_else(|| config.model.name.clone());

    // -----------------------------------------------------------------------
    // Pre-flight: registration → model check → MCP servers
    // (runecode only talks to Core for registration, then exclusively to the
    //  AI service — the Ollama wrapper — for everything else)
    // -----------------------------------------------------------------------

    // 1. Register with RuneCore Core (blocking, confirmed)
    if config.runecore.register {
        let registered = register_and_confirm(&config.runecore.core_url).await;
        if !registered {
            println!("  \x1b[31m✗\x1b[0m  RuneCore Core unreachable at {}", config.runecore.core_url);
            println!("      Is the ecosystem running? (docker compose up -d)");
            return Ok(());
        }
    }

    // 2. Connect to AI service and verify model is available
    let client = OllamaClient::new(config.model.wrapper_url.clone());
    match client.available_models().await {
        Ok(models) => {
            if models.contains(&model) {
                println!("  \x1b[32m✓\x1b[0m  AI service ready  ({})", model);
            } else {
                println!("  \x1b[33m?\x1b[0m  Model '{}' not found in Ollama.", model);
                if !models.is_empty() {
                    println!("      Available: {}", models.join(", "));
                }

                print!("\n  Download '{}' now? [y/N] ", model);
                io::stdout().flush().ok();

                let mut answer = String::new();
                let do_download = match io::stdin().lock().read_line(&mut answer) {
                    Ok(_) => answer.trim().eq_ignore_ascii_case("y"),
                    Err(_) => false,
                };

                if !do_download {
                    if !models.is_empty() {
                        println!("  Tip: override model with  runecode -m {}", models[0]);
                    }
                    return Ok(());
                }

                println!("\n  Starting download...");
                if let Err(e) = client.pull_model(&model).await {
                    println!("  \x1b[31m✗\x1b[0m  Could not start download: {e}");
                    return Ok(());
                }

                // Live progress bar — polls /api/pulls/<model> every 600 ms
                loop {
                    tokio::time::sleep(std::time::Duration::from_millis(600)).await;
                    match client.poll_pull(&model).await {
                        Ok((status, progress)) => {
                            let filled = (progress as usize * 20) / 100;
                            let bar = format!(
                                "[{}{}] {:>3}%",
                                "\u{2588}".repeat(filled),
                                "\u{2591}".repeat(20 - filled),
                                progress,
                            );
                            print!("\r  \x1b[34m⬇\x1b[0m  {bar}  ");
                            io::stdout().flush().ok();

                            match status.as_str() {
                                "completed" => {
                                    println!("\n  \x1b[32m✓\x1b[0m  Download complete");
                                    break;
                                }
                                "failed" => {
                                    println!("\n  \x1b[31m✗\x1b[0m  Download failed");
                                    return Ok(());
                                }
                                _ => {} // "running" / "starting" — keep polling
                            }
                        }
                        Err(_) => {
                            // Briefly unavailable right after start — keep polling
                        }
                    }
                }
            }
        }
        Err(e) => {
            println!("  \x1b[31m✗\x1b[0m  AI service unreachable: {e}");
            println!("      Is RuneCore_AI running? (cd projects/RuneCore_AI && docker compose -f docker-compose.dev.yml up -d)");
            return Ok(());
        }
    }

    // 3. Connect to any configured external MCP servers
    let mut mcp = mcp_client::connect_all(&config.mcp_servers).await;

    // -----------------------------------------------------------------------
    // Build context + tools
    // -----------------------------------------------------------------------

    let project = context::build(&cwd, &config);
    let mut gate = ApprovalGate::new(config.approval.clone(), cli.auto, cli.safe);

    // Built-in tool definitions + any tools from external MCP servers
    let mut tool_defs: Vec<Value> = tools::all_tools()
        .iter()
        .map(|t| tools::tool_to_json(t))
        .collect();
    tool_defs.extend(mcp.all_schemas());

    // Seed conversation
    let mut messages: Vec<Value> = vec![serde_json::json!({
        "role": "system",
        "content": project.system_prompt
    })];

    display::print_header(&model, &project.root.to_string_lossy());

    // -----------------------------------------------------------------------
    // Ctrl+C cancellation — broadcast channel so every in-flight request can
    // subscribe and abort cleanly without killing the whole process.
    // -----------------------------------------------------------------------
    let (cancel_tx, _) = broadcast::channel::<()>(4);
    {
        let tx = cancel_tx.clone();
        tokio::spawn(async move {
            loop {
                if tokio::signal::ctrl_c().await.is_ok() {
                    // Ignore send errors — no active receivers means nobody is
                    // waiting on a request right now (user is at the prompt).
                    let _ = tx.send(());
                }
            }
        });
    }

    // -----------------------------------------------------------------------
    // One-shot task
    // -----------------------------------------------------------------------
    if let Some(task) = cli.task {
        run_turn(
            &client,
            &mut messages,
            &tool_defs,
            &task,
            &model,
            &cwd,
            &mut gate,
            &mut mcp,
            config.model.temperature,
            cancel_tx.subscribe(),
        )
        .await?;
        return Ok(());
    }

    // -----------------------------------------------------------------------
    // Interactive loop
    // -----------------------------------------------------------------------
    let stdin = io::stdin();
    loop {
        display::print_prompt();

        let mut input = String::new();
        match stdin.lock().read_line(&mut input) {
            Ok(0) => break, // EOF (also what Ctrl+C triggers at the prompt on Windows)
            Ok(_) => {}
            Err(_) => break,
        }

        let input = input.trim().to_string();
        if input.is_empty() {
            continue;
        }
        if matches!(input.as_str(), "/exit" | "/quit" | "exit" | "quit") {
            break;
        }

        println!();

        run_turn(
            &client,
            &mut messages,
            &tool_defs,
            &input,
            &model,
            &cwd,
            &mut gate,
            &mut mcp,
            config.model.temperature,
            cancel_tx.subscribe(),
        )
        .await?;
    }

    println!("\nGoodbye.");
    Ok(())
}

// ---------------------------------------------------------------------------
// One conversation turn — full tool-call loop
// ---------------------------------------------------------------------------

async fn run_turn(
    client: &OllamaClient,
    messages: &mut Vec<Value>,
    tool_defs: &[Value],
    user_input: &str,
    model: &str,
    cwd: &PathBuf,
    gate: &mut ApprovalGate,
    mcp: &mut McpRegistry,
    temperature: f64,
    mut cancel: broadcast::Receiver<()>,
) -> Result<()> {
    messages.push(serde_json::json!({
        "role": "user",
        "content": user_input
    }));

    // Deduplication cache: "tool_name:args_json" → result
    // Prevents the model from calling the same tool repeatedly with identical args.
    let mut tool_call_cache: std::collections::HashMap<String, String> = std::collections::HashMap::new();
    let mut iteration: u32 = 0;
    const MAX_ITERATIONS: u32 = 20;

    loop {
        iteration += 1;
        if iteration > MAX_ITERATIONS {
            eprintln!("\n  \x1b[33m⚠\x1b[0m  Stopped after {MAX_ITERATIONS} tool calls — model may be stuck.");
            break;
        }

        display::print_thinking();

        let req = AgentRequest {
            model: model.to_string(),
            messages: messages.clone(),
            tools: Some(tool_defs.to_vec()),
            stream: false,
            temperature: Some(temperature),
        };

        let response = tokio::select! {
            // Normal path: LLM responds
            res = client.agent(req) => match res {
                Ok(r) => r,
                Err(e) => {
                    display::clear_thinking();
                    let msg = e.to_string();
                    if msg.contains("404") {
                        eprintln!("\n  Model not found — is '{model}' downloaded in Ollama?");
                    } else if msg.contains("502") || msg.contains("503") {
                        eprintln!("\n  AI service error — check docker logs for ollama_wrapper");
                    } else {
                        eprintln!("\n  Error: {e}");
                    }
                    return Ok(());
                }
            },
            // Ctrl+C: drop the in-flight HTTP request and return to the prompt
            _ = cancel.recv() => {
                display::clear_thinking();
                println!("\n  Cancelled.");
                return Ok(());
            }
        };

        display::clear_thinking();

        // Handle tool calls
        if let Some(tool_calls) = &response.tool_calls {
            if !tool_calls.is_empty() {
                if response.promoted {
                    // Model emitted the tool call as plain-text JSON (no native tool support).
                    // Keep the original JSON as the assistant message so the model recognises
                    // its own output in history. Tool results go back as `role: "user"` because
                    // text-format models don't understand `role: "tool"`.
                    messages.push(serde_json::json!({
                        "role": "assistant",
                        "content": response.content.clone().unwrap_or_default(),
                    }));
                } else {
                    // Native tool calling — use the structured format Ollama expects.
                    messages.push(serde_json::json!({
                        "role": "assistant",
                        "content": response.content.clone().unwrap_or_default(),
                        "tool_calls": tool_calls.iter().map(|tc| serde_json::json!({
                            "id": tc.id,
                            "type": "function",
                            "function": { "name": tc.name, "arguments": tc.arguments }
                        })).collect::<Vec<_>>()
                    }));
                }

                for tc in tool_calls {
                    let args_display = ApprovalGate::format_args(&tc.arguments);

                    if !gate.check(&tc.name, &args_display) {
                        display::print_tool_denied(&tc.name);
                        if response.promoted {
                            messages.push(serde_json::json!({
                                "role": "user",
                                "content": format!("Tool '{}' was denied by the user.", tc.name)
                            }));
                        } else {
                            messages.push(serde_json::json!({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": "Tool call denied by user"
                            }));
                        }
                        continue;
                    }

                    if gate.is_auto(&tc.name) {
                        display::print_tool_exec(&tc.name, &args_display);
                    }

                    // Deduplication: if we already ran this exact call, inject the cached
                    // result with an insistent "stop repeating yourself" message.
                    let cache_key = format!("{}:{}", tc.name, tc.arguments);
                    if let Some(cached) = tool_call_cache.get(&cache_key) {
                        let force = format!(
                            "You already called `{}` with these arguments and got this result:\n{}\n\n\
                             Do NOT call this tool again. Use these results and answer in plain English now.",
                            tc.name, cached
                        );
                        display::print_tool_result(&tc.name, "(cached — duplicate call)", false);
                        if response.promoted {
                            messages.push(serde_json::json!({"role": "user", "content": force}));
                        } else {
                            messages.push(serde_json::json!({"role": "tool", "tool_call_id": tc.id, "content": force}));
                        }
                        continue;
                    }

                    // Route: external MCP server or built-in
                    let (result, is_error) = if mcp.owns(&tc.name) {
                        mcp.execute(&tc.name, tc.arguments.clone()).await
                    } else {
                        tools::execute(&tc.name, tc.arguments.clone(), cwd).await
                    };

                    let preview: String = result.lines().next().unwrap_or("").chars().take(80).collect();
                    display::print_tool_result(&tc.name, &preview, is_error);

                    // Cache result so duplicate calls are caught above.
                    tool_call_cache.insert(cache_key, result.clone());

                    if response.promoted {
                        // Inject result as a user message so the model sees it in history.
                        messages.push(serde_json::json!({
                            "role": "user",
                            "content": format!("Tool result for {}:\n{}", tc.name, result)
                        }));
                    } else {
                        messages.push(serde_json::json!({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result
                        }));
                    }
                }

                continue; // Get the next LLM response
            }
        }

        // No tool calls — print final text response
        let content = response.content.unwrap_or_default();
        if !content.is_empty() {
            println!("\n{content}");
        }

        messages.push(serde_json::json!({
            "role": "assistant",
            "content": content
        }));

        break;
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// --delete: clean up runecode's own runtime footprint
// ---------------------------------------------------------------------------

async fn run_delete(cwd: &PathBuf) -> Result<()> {
    println!("Cleaning up RuneDev_Code runtime files...\n");

    let mut removed_any = false;

    // 1. Global config/data directory: ~/.config/runecode/
    if let Some(dir) = Config::global_config_dir() {
        if dir.exists() {
            match std::fs::remove_dir_all(&dir) {
                Ok(_) => {
                    println!("  \x1b[32m✓\x1b[0m Removed global config: {}", dir.display());
                    removed_any = true;
                }
                Err(e) => println!("  \x1b[31m✗\x1b[0m Failed to remove {}: {e}", dir.display()),
            }
        } else {
            println!("  \x1b[2m—\x1b[0m Global config dir not present: {}", dir.display());
        }
    }

    // 2. Local project config: .runecode.toml in cwd (if the user generated one)
    let local_cfg = cwd.join(".runecode.toml");
    if local_cfg.exists() {
        match std::fs::remove_file(&local_cfg) {
            Ok(_) => {
                println!("  \x1b[32m✓\x1b[0m Removed local config: {}", local_cfg.display());
                removed_any = true;
            }
            Err(e) => println!("  \x1b[31m✗\x1b[0m Failed to remove {}: {e}", local_cfg.display()),
        }
    } else {
        println!("  \x1b[2m—\x1b[0m No local .runecode.toml found in {}", cwd.display());
    }

    println!();
    if removed_any {
        println!("Done. To also remove the binary, run:  bash manage.sh -d");
    } else {
        println!("Nothing to clean up.");
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// Core registration — blocking, confirmed before proceeding
// ---------------------------------------------------------------------------

/// Attempts to register with RuneCore Core. Returns true if confirmed.
async fn register_and_confirm(core_url: &str) -> bool {
    // Core uses a self-signed TLS cert — accept it for local registration.
    // mTLS client certs are not required when RUNECORE_DISABLE_MTLS=1 (dev default).
    let client = match reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(5))
        .danger_accept_invalid_certs(true)
        .build()
    {
        Ok(c) => c,
        Err(_) => return false,
    };

    let hostname = gethostname();
    let payload = serde_json::json!({
        "name": "RuneDevCode",
        "version": env!("CARGO_PKG_VERSION"),
        "rest_url": "local",
        "dependencies": [],
        "container_name": hostname
    });

    print!("  \x1b[2m◦\x1b[0m  Registering with RuneCore Core...");

    for attempt in 0..3u32 {
        match client
            .post(&format!("{core_url}/api/v1/services/register"))
            .json(&payload)
            .send()
            .await
        {
            Ok(r) if r.status().is_success() => {
                print!("\r");
                println!("  \x1b[32m✓\x1b[0m  Registered with Core");
                return true;
            }
            _ => {}
        }
        if attempt < 2 {
            tokio::time::sleep(std::time::Duration::from_secs(u64::from(attempt) + 1)).await;
        }
    }

    print!("\r");
    false
}

fn gethostname() -> String {
    std::env::var("COMPUTERNAME")
        .or_else(|_| std::env::var("HOSTNAME"))
        .unwrap_or_else(|_| "runecode-host".to_string())
}
