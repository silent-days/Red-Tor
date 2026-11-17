#!/usr/bin/env bash
set -Eeuo pipefail
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
if [[ "$(uname -s)" != Linux ]]; then
    echo "ERROR: Linux only." >&2
    exit 1
fi
if [[ "${1:-}" != "--yes" ]]; then
    echo "This removes the Red Tor application, virtual environment, and launchers."
    echo "It preserves ~/.silent-tor notes/settings and ~/.local/state/red-tor Tor runtime state."
    read -r -p "Continue? [y/N] " answer
    [[ "$answer" =~ ^[Yy]$ ]] || { echo "Cancelled."; exit 0; }
fi
rm -rf -- "$DATA_HOME/red-tor" "$DATA_HOME/red-tor.previous"
rm -f -- "$BIN_DIR/red-tor" "$BIN_DIR/red-tor-uninstall" \
    "$DATA_HOME/applications/red-tor.desktop" \
    "$CONFIG_HOME/autostart/red-tor.desktop"
echo "Red Tor app files removed. Local notes/settings and Tor runtime state were preserved."
