#!/usr/bin/env bash
# setup.sh - One-shot setup for the Second Brain system
# Run once after a fresh clone/install.
# Usage: bash ~/Second-Brain/scripts/setup.sh

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
warn() { echo -e "${YELLOW}  ⚠${NC} $*"; }
fail() { echo -e "${RED}  ✗${NC} $*"; }

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Second Brain – Setup Script                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. System packages ─────────────────────────────────────────────────────
echo "▶ Checking system packages..."
if command -v inotifywait &>/dev/null; then
    ok "inotify-tools already installed"
else
    warn "inotify-tools missing – installing (needs sudo)..."
    sudo apt-get install -y inotify-tools
    ok "inotify-tools installed"
fi

# ── 2. Python packages ─────────────────────────────────────────────────────
echo ""
echo "▶ Checking Python packages..."
for pkg in chromadb ollama chroma-mcp; do
    if pip3 show "$pkg" &>/dev/null; then
        ver=$(pip3 show "$pkg" 2>/dev/null | grep Version | awk '{print $2}')
        ok "$pkg $ver"
    else
        warn "$pkg missing – installing..."
        pip3 install --user --break-system-packages "$pkg"
        ok "$pkg installed"
    fi
done

# ── 3. Ollama service ──────────────────────────────────────────────────────
echo ""
echo "▶ Checking Ollama server..."
if ollama list &>/dev/null; then
    ok "Ollama is running"
else
    warn "Ollama not running – starting..."
    ollama serve > /tmp/ollama.log 2>&1 &
    sleep 4
    if ollama list &>/dev/null; then
        ok "Ollama started (background)"
    else
        fail "Could not start Ollama. Start manually: ollama serve"
        exit 1
    fi
fi

# ── 4. Embedding model ─────────────────────────────────────────────────────
echo ""
echo "▶ Checking embedding model (mxbai-embed-large)..."
if ollama list 2>/dev/null | grep -q "mxbai-embed-large"; then
    ok "mxbai-embed-large already pulled"
else
    warn "Pulling mxbai-embed-large (~670 MB)..."
    ollama pull mxbai-embed-large
    ok "mxbai-embed-large ready"
fi

# ── 5. Ollama autostart ────────────────────────────────────────────────────
echo ""
echo "▶ Configuring Ollama autostart (systemd user)..."
SERVICE="$HOME/.config/systemd/user/ollama.service"
if systemctl --user is-enabled ollama &>/dev/null; then
    ok "Ollama systemd user service already enabled"
else
    mkdir -p "$HOME/.config/systemd/user"
    cat > "$SERVICE" << 'UNIT'
[Unit]
Description=Ollama AI Model Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/ollama serve
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
UNIT
    systemctl --user daemon-reload
    systemctl --user enable ollama
    ok "Ollama systemd user service enabled"
fi

# ── 6. Initial vault index ─────────────────────────────────────────────────
echo ""
echo "▶ Running initial vault index..."
python3 "$(dirname "$0")/index_vault.py"

# ── 7. Summary ─────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Setup Complete! Next steps:                     ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  1. Restart Claude Desktop to load the MCP      ║"
echo "║     second-brain-chroma server.                  ║"
echo "║                                                  ║"
echo "║  2. Start the file watcher (optional):           ║"
echo "║     bash ~/Second-Brain/scripts/watch_vault.sh   ║"
echo "║                                                  ║"
echo "║  3. Test retrieval:                              ║"
echo "║     python3 ~/Second-Brain/scripts/retrieve.py   ║"
echo "║       \"what is my second brain?\"                 ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
