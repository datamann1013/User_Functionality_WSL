# RuneDev_Code (`runecode`)

Native Rust coding agent for the RuneCore ecosystem. Two modes:

- **Agent**: interactive / one-shot coding agent driven by local Ollama via the
  RuneCore_Mind wrapper.
- **MCP server** (`runecode --mcp-server`): exposes its file/shell/search/git
  tools over the Model Context Protocol for Claude Code or any MCP client.

## Build

```bash
cargo build --release      # -> target/release/runecode(.exe)
cargo test                 # unit tests incl. security guardrails
```

## Tools

`read_file`, `write_file`, `create_file`, `delete_file`, `list_directory`,
`run_bash`, `search_files`, `search_in_files`, `git_status`, `git_diff`,
`git_log`.

## Security model

`runecode` can execute commands and modify files, so it ships with two
independent layers. **Treat the container / sandbox as the real boundary; the
in-binary guardrails are defence-in-depth for when you run it directly.**

### Layer 1 — in-binary guardrails (`src/security.rs`)

- **Path sandbox**: `read/write/create/delete/list` are confined to a root
  (default = project cwd). Absolute paths, `..` traversal, and symlink escapes
  resolving outside the root are rejected.
- **Command policy**: `run_bash` is checked against a builtin denylist
  (`rm -rf /`, `mkfs`, `dd of=/dev/*`, fork bombs, `format C:`, pipe-to-shell,
  `shutdown`/`reboot`) plus any user patterns, with an optional allowlist.

Configure under `[security]` in `.runecode.toml` (see `config.example.toml`):

```toml
[security]
sandbox_root       = ""      # empty = project root
allow_outside_root = false
shell_denylist     = []      # extra regexes, merged with builtins
shell_allowlist    = []      # if set, commands must match one
```

> The approval gate (`[approval]`) is a **UX confirmation**, not a security
> boundary — `--auto` bypasses it. Do not rely on it for isolation.

### Layer 2 — OS-level isolation (recommended)

**Docker (Linux/Windows/macOS):**

```bash
RUNECODE_WORKSPACE=/path/to/project docker compose run --rm runecode
# MCP server:
RUNECODE_WORKSPACE=/path/to/project docker compose run --rm runecode --mcp-server
```

The container runs as non-root, drops all capabilities, `no-new-privileges`,
and defaults to **no network**. Only the mounted `/workspace` is writable.
Enable networking only if the agent must reach the RuneCore_Mind wrapper or
register with Core (uncomment `network_mode` in `docker-compose.yml`).

**Windows Sandbox (native, ephemeral VM):**

```powershell
.\run_sandboxed.ps1 -Workspace C:\code\my-project
```

Maps only the project folder (read-write) and `runecode.exe` (read-only) into a
disposable sandbox; everything else on the host is invisible and the VM is
destroyed on close. Requires the "Windows Sandbox" optional feature.

## Configuration

`.runecode.toml` in the project root, or `~/.config/runecode/config.toml`
globally. See `config.example.toml` for all options.
