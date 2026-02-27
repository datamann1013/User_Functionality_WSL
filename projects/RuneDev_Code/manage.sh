#!/usr/bin/env bash
# manage.sh — Build, install, or uninstall RuneDev_Code
#
# Flags (can be combined as -ci or passed separately):
#   -c   Compile (cargo build --release)
#   -i   Install (verify binary then copy to INSTALL_DIR)
#   -d   Delete/uninstall from INSTALL_DIR
#
# Environment:
#   RUNECODE_INSTALL_DIR  Override install directory (default: ~/.cargo/bin)
#   CARGO                 Override cargo binary path

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect Windows (Git Bash / MSYS2 / Cygwin)
if [[ "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* || -n "${WINDIR:-}" ]]; then
    BIN_EXT=".exe"
else
    BIN_EXT=""
fi

BINARY_NAME="runecode${BIN_EXT}"
BUILD_BIN="$SCRIPT_DIR/target/release/$BINARY_NAME"
INSTALL_DIR="${RUNECODE_INSTALL_DIR:-$HOME/.cargo/bin}"
INSTALL_BIN="$INSTALL_DIR/$BINARY_NAME"
MIN_SIZE_BYTES=102400  # 100 KB — any Rust release binary will be larger

# Locate cargo
if [[ -n "${CARGO:-}" ]]; then
    : # use as-is
elif command -v cargo &>/dev/null; then
    CARGO="cargo"
elif [[ -x "$HOME/.cargo/bin/cargo" ]]; then
    CARGO="$HOME/.cargo/bin/cargo"
else
    echo "✗ cargo not found. Install Rust from https://rustup.rs/" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Colour helpers (degrade gracefully when not a TTY)
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
    _g='\e[32m' _r='\e[31m' _y='\e[33m' _b='\e[34m' _d='\e[2m' _B='\e[1m' _0='\e[0m'
else
    _g='' _r='' _y='' _b='' _d='' _B='' _0=''
fi
green() { echo -e "${_g}$*${_0}"; }
red()   { echo -e "${_r}$*${_0}"; }
yellow(){ echo -e "${_y}$*${_0}"; }
dim()   { echo -e "${_d}$*${_0}"; }
bold()  { echo -e "${_B}$*${_0}"; }

# ---------------------------------------------------------------------------
# Verify a runecode binary is present, sane-sized, and executable
# ---------------------------------------------------------------------------
verify_binary() {
    local bin="$1"

    if [[ ! -f "$bin" ]]; then
        red "  ✗ Not found: $bin"
        return 1
    fi

    local size
    size=$(wc -c < "$bin" | tr -d ' ')
    if (( size < MIN_SIZE_BYTES )); then
        red "  ✗ Binary is only ${size} bytes — likely corrupt or incomplete"
        return 1
    fi

    local ver
    if ! ver=$("$bin" --version 2>&1); then
        red "  ✗ Binary failed to execute (--version returned non-zero)"
        return 1
    fi

    green "  ✓ OK: $ver  (${size} bytes)"
    return 0
}

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
do_compile() {
    bold "\n${_b}◆${_0} Compiling RuneDev_Code..."
    dim "  manifest : $SCRIPT_DIR/Cargo.toml"
    dim "  cargo    : $CARGO"
    echo ""

    "$CARGO" build --release --manifest-path "$SCRIPT_DIR/Cargo.toml"

    echo ""
    if [[ -f "$BUILD_BIN" ]]; then
        local size
        size=$(wc -c < "$BUILD_BIN" | tr -d ' ')
        green "  ✓ Compiled: $BUILD_BIN  (${size} bytes)"
    else
        red "  ✗ Build reported success but binary is missing: $BUILD_BIN"
        exit 1
    fi
}

do_install() {
    bold "\n${_b}◆${_0} Installing RuneDev_Code..."
    dim "  source : $BUILD_BIN"
    dim "  target : $INSTALL_BIN"
    echo ""

    echo "  Verifying build binary..."
    if ! verify_binary "$BUILD_BIN"; then
        echo ""
        red "  Cannot install — run with -c first to compile"
        exit 1
    fi

    if [[ ! -d "$INSTALL_DIR" ]]; then
        yellow "  Install directory does not exist — creating it..."
        mkdir -p "$INSTALL_DIR"
    fi

    if [[ -f "$INSTALL_BIN" ]]; then
        local old_ver
        old_ver=$("$INSTALL_BIN" --version 2>&1 || echo "unknown")
        yellow "  Previous install found ($old_ver) — replacing..."
        rm "$INSTALL_BIN"
    fi

    cp "$BUILD_BIN" "$INSTALL_BIN"

    echo ""
    echo "  Verifying installed binary..."
    if verify_binary "$INSTALL_BIN"; then
        echo ""
        green "  ✓ Installed to $INSTALL_BIN"
        dim   "  Run 'runecode --help' to get started"
    else
        red "  ✗ Installed binary failed verification — something went wrong"
        exit 1
    fi
}

do_delete() {
    bold "\n${_b}◆${_0} Uninstalling RuneDev_Code..."
    dim "  location: $INSTALL_BIN"
    echo ""

    if [[ -f "$INSTALL_BIN" ]]; then
        rm "$INSTALL_BIN"
        green "  ✓ Removed: $INSTALL_BIN"
    else
        yellow "  Nothing to remove — not installed at $INSTALL_BIN"
    fi
}

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
    bold "Usage: $(basename "$0") [-c] [-i] [-d]"
    echo ""
    echo "  -c   Compile (cargo build --release)"
    echo "  -i   Install — verify build binary then copy to install dir"
    echo "  -d   Delete — remove installed binary"
    echo ""
    echo "  -ci  Compile then install (most common)"
    echo ""
    bold "Install directory"
    dim  "  Default : ~/.cargo/bin  (already on PATH for Cargo users)"
    dim  "  Override: export RUNECODE_INSTALL_DIR=/your/path"
    echo ""
    bold "Examples"
    dim  "  ./manage.sh -ci        # full build + install"
    dim  "  ./manage.sh -c         # build only"
    dim  "  ./manage.sh -i         # verify existing build and install"
    dim  "  ./manage.sh -d         # uninstall"
}

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------
DO_COMPILE=0
DO_INSTALL=0
DO_DELETE=0

if [[ $# -eq 0 ]]; then
    usage
    exit 0
fi

for arg in "$@"; do
    case "$arg" in
        -*)
            [[ "$arg" == *c* ]] && DO_COMPILE=1
            [[ "$arg" == *i* ]] && DO_INSTALL=1
            [[ "$arg" == *d* ]] && DO_DELETE=1
            ;;
        *)
            red "Unknown argument: $arg"
            echo ""
            usage
            exit 1
            ;;
    esac
done

if [[ $DO_DELETE -eq 1 && ($DO_COMPILE -eq 1 || $DO_INSTALL -eq 1) ]]; then
    red "✗ -d (delete) cannot be combined with -c or -i"
    exit 1
fi

if [[ $DO_COMPILE -eq 0 && $DO_INSTALL -eq 0 && $DO_DELETE -eq 0 ]]; then
    red "✗ No valid flags found"
    echo ""
    usage
    exit 1
fi

# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------
[[ $DO_COMPILE -eq 1 ]] && do_compile
[[ $DO_INSTALL -eq 1 ]] && do_install
[[ $DO_DELETE -eq 1 ]]  && do_delete

echo ""
bold "Done."
