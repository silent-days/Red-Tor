#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(uname -s)" != Linux ]]; then
    echo "ERROR: Red Tor currently supports Linux only." >&2
    exit 1
fi
if [[ "$(id -u)" -eq 0 ]]; then
    [[ -x "$SCRIPT_DIR/install-system.sh" ]] || { echo "ERROR: system installer is missing." >&2; exit 1; }
    exec "$SCRIPT_DIR/install-system.sh" "$@"
fi
echo "No sudo detected: installing per-user (no root needed) into ~/.local/share/red-tor."
exec "$SCRIPT_DIR/install-user.sh" --autostart "$@"
