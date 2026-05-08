#!/usr/bin/env bash
# watch_vault.sh - Watch ~/Second-Brain/ for .md file changes and re-index
#
# Usage: bash ~/Second-Brain/scripts/watch_vault.sh
# Requires: inotifywait (apt install inotify-tools)

set -euo pipefail

VAULT_DIR="$HOME/Second-Brain"
SCRIPT="$HOME/Second-Brain/scripts/index_vault.py"
PYTHON="${PYTHON:-python3}"

# Verify dependencies
if ! command -v inotifywait &>/dev/null; then
    echo "[ERROR] inotifywait not found. Install with: sudo apt install inotify-tools"
    exit 1
fi

if ! command -v "$PYTHON" &>/dev/null; then
    echo "[ERROR] Python not found at: $PYTHON"
    exit 1
fi

echo "╔══════════════════════════════════════════════════╗"
echo "║  Second Brain – Vault Watcher                    ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Vault   : $VAULT_DIR"
echo "  Script  : $SCRIPT"
echo "  Watching for .md file changes... (Ctrl+C to stop)"
echo ""

# Track last index time to debounce rapid saves
LAST_INDEX=0
DEBOUNCE_SECS=3

do_index() {
    local file="$1"
    local now
    now=$(date +%s)

    if (( now - LAST_INDEX < DEBOUNCE_SECS )); then
        echo "[$(date '+%H:%M:%S')] Debounced rapid save: $file"
        return
    fi
    LAST_INDEX=$now

    echo ""
    echo "[$(date '+%H:%M:%S')] Change detected: $file"
    echo "[$(date '+%H:%M:%S')] Re-indexing vault..."
    "$PYTHON" "$SCRIPT"
    echo "[$(date '+%H:%M:%S')] ✓ Index updated."
    echo ""
}

# Watch recursively; react to close_write (file saved) and move events
inotifywait \
    --recursive \
    --monitor \
    --quiet \
    --format '%w%f %e' \
    --event close_write,moved_to \
    --include '\.md$' \
    "$VAULT_DIR" |
while IFS= read -r line; do
    filepath="${line% *}"
    # Double-check it ends in .md (inotifywait --include is a regex filter)
    if [[ "$filepath" == *.md ]]; then
        do_index "$filepath"
    fi
done
