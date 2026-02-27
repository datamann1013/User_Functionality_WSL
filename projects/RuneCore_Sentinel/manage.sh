#!/usr/bin/env bash
# manage.sh — RuneSentry build / install / uninstall
#
# Usage:
#   ./manage.sh -c       Compile (cargo build --release)
#   ./manage.sh -i       Install compiled binary → PATH + Windows startup
#   ./manage.sh -d       Delete / uninstall (remove binary from PATH + startup entry)
#   ./manage.sh -ic      Compile then install (most common workflow)
#
# The installed binary is named RuneSentry and placed in ~/.cargo/bin so it is
# already on PATH for users who have Rust installed.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY_NAME="RuneSentry"
INSTALL_DIR="$HOME/.cargo/bin"
BINARY_SRC="$SCRIPT_DIR/target/release/${BINARY_NAME}.exe"
BINARY_DST="$INSTALL_DIR/${BINARY_NAME}.exe"

# Windows registry key for per-user startup programs
REG_KEY='HKCU\Software\Microsoft\Windows\CurrentVersion\Run'
REG_NAME="RuneSentry"

# ── Helpers ──────────────────────────────────────────────────────────────────

log()  { echo "  $*"; }
ok()   { echo "  ✓ $*"; }
warn() { echo "  ⚠ $*"; }
err()  { echo "  ✗ $*" >&2; }

# Convert a Unix-style path to a Windows backslash path.
# Tries cygpath (Git for Windows / Cygwin), falls back to sed.
to_win_path() {
    local p="$1"
    if command -v cygpath &>/dev/null; then
        cygpath -w "$p"
    else
        # MINGW / Git Bash fallback: /c/foo → C:\foo
        echo "$p" | sed 's|^/\([a-zA-Z]\)/|\1:\\|;s|/|\\|g'
    fi
}

# ── Actions ───────────────────────────────────────────────────────────────────

do_compile() {
    log "Compiling RuneSentry (release)…"
    cd "$SCRIPT_DIR"
    cargo build --release
    ok "Compiled: $BINARY_SRC"
}

do_install() {
    # Verify binary exists
    if [[ ! -f "$BINARY_SRC" ]]; then
        err "Binary not found at: $BINARY_SRC"
        err "Run ./manage.sh -c first to compile."
        exit 1
    fi

    # Warn if a previous install exists
    if [[ -f "$BINARY_DST" ]]; then
        warn "Previous install detected at $BINARY_DST — overwriting."
    fi

    # Copy binary to install dir
    mkdir -p "$INSTALL_DIR"
    cp "$BINARY_SRC" "$BINARY_DST"
    ok "Installed: $BINARY_DST"

    # Register Windows startup (runs RuneSentry on every login)
    local win_path
    win_path="$(to_win_path "$BINARY_DST")"

    if reg add "$REG_KEY" /v "$REG_NAME" /t REG_SZ /d "\"${win_path}\"" /f &>/dev/null; then
        ok "Registered Windows startup entry (runs on login)"
    else
        warn "Could not write to registry — startup entry NOT set."
        warn "You can start RuneSentry manually: $BINARY_NAME"
    fi

    echo ""
    log "Done. RuneSentry is now:"
    log "  • Installed in PATH as '${BINARY_NAME}'"
    log "  • Registered to start on Windows login"
    log ""
    log "To start now:   RuneSentry"
    log "To uninstall:   RuneSentry --delete   OR   ./manage.sh -d"
}

do_delete() {
    log "Uninstalling RuneSentry…"

    # Remove from Windows startup
    if reg delete "$REG_KEY" /v "$REG_NAME" /f &>/dev/null; then
        ok "Removed Windows startup entry"
    else
        warn "Startup entry not found (already removed or never installed)"
    fi

    # Remove binary from install dir
    if [[ -f "$BINARY_DST" ]]; then
        rm -f "$BINARY_DST"
        ok "Removed binary: $BINARY_DST"
    else
        warn "Binary not found at $BINARY_DST (already removed?)"
    fi

    echo ""
    ok "RuneSentry uninstalled."
    log "(Source code and build artefacts in $SCRIPT_DIR are untouched)"
}

usage() {
    cat <<EOF

  RuneSentry — manage.sh

  Usage: ./manage.sh [OPTION]

  Options:
    -c        Compile (cargo build --release)
    -i        Install compiled binary to PATH + register Windows startup
    -d        Delete / uninstall (remove binary and startup entry)
    -ic       Compile then install  [most common]

  Examples:
    ./manage.sh -ic          # build and install
    ./manage.sh -c           # just compile
    ./manage.sh -i           # install an already-compiled binary
    ./manage.sh -d           # uninstall
    RuneSentry --delete      # self-uninstall (same as -d, with y/n prompt)

EOF
}

# ── Argument dispatch ─────────────────────────────────────────────────────────

if [[ $# -eq 0 ]]; then
    usage
    exit 0
fi

case "$1" in
    -c)   do_compile ;;
    -i)   do_install ;;
    -d)   do_delete  ;;
    -ic)  do_compile; echo ""; do_install ;;
    *)
        err "Unknown option: $1"
        usage
        exit 1
        ;;
esac
