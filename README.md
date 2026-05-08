# 🧠 Second Brain — Complete System Reference

> **System Status:** ✅ Fully operational as of 2026-05-08  
> **Location:** `/home/ab/Second-Brain/`  
> **Owner:** ab (local machine, 100% private)

---

## 1. What This System Is

A **fully local, private, AI-powered semantic knowledge retrieval system** built on your laptop.  
No cloud. No API keys. No subscriptions. No data leaves your machine.

You write Markdown notes → an AI pipeline converts them to math vectors → Claude Desktop can search them in real-time using natural language.

---

## 2. Current System Stats (Live)

| Metric | Value |
|---|---|
| Vault location | `~/Second-Brain/` |
| Total vault size (notes) | ~140 KB |
| Total markdown files indexed | **5 files** |
| Total vector chunks in ChromaDB | **12 chunks** |
| Vector dimensions | **1024** (mxbai-embed-large) |
| Similarity space | Cosine |
| Index size on disk | **1.7 MB** |
| Embedding model | `mxbai-embed-large:latest` (669 MB) |
| Ollama version | `0.20.4` client / `0.6.1` Python SDK |
| ChromaDB version | `1.5.9` |
| chroma-mcp version | `0.2.6` |
| Python version | `3.12.3` |
| MCP servers in Claude Desktop | 5 (ollama, filesystem, desktop-commander, excalidraw, **second-brain-chroma**) |

### Indexed Files Breakdown

| File | Chunks | ~Words |
|---|---|---|
| `00-Core/system-prompt.md` | 4 | 665 |
| `02-Knowledge/Second-Brain-Architecture.md` | 3 | 467 |
| `02-Knowledge/MCP-Setup.md` | 2 | 389 |
| `03-Memory/Ollama-Setup.md` | 2 | 329 |
| `00-Core/Templates/default.md` | 1 | 51 |

---

## 3. Full Directory Structure

```
~/Second-Brain/
│
├── 00-Core/                    ← System configuration & templates
│   ├── system-prompt.md        ← Claude Desktop system prompt (paste into settings)
│   └── Templates/
│       └── default.md          ← Frontmatter template for new notes
│
├── 01-Projects/                ← Active project notes (one folder per project)
├── 02-Knowledge/               ← Permanent reference knowledge (stays forever)
│   ├── Second-Brain-Architecture.md
│   └── MCP-Setup.md
│
├── 03-Memory/                  ← Personal episodic memory, setup experiences
│   └── Ollama-Setup.md
│
├── 04-Context/                 ← Current sprint / active focus window
├── 05-Daily/                   ← Daily journals, meeting notes (YYYY-MM-DD.md)
├── 06-AI-Memory/               ← AI-distilled insight nuggets (written by Claude)
│
├── .indexes/
│   └── chroma/                 ← ChromaDB persistent vector database
│       ├── chroma.sqlite3      ← Main SQLite store (440 KB)
│       └── [uuid-dirs]/        ← HNSW index shards
│
├── embeddings/                 ← Reserved for future embedding cache
│
└── scripts/
    ├── index_vault.py          ← Chunk + embed + store all .md files
    ├── retrieve.py             ← Semantic search CLI tool
    ├── watch_vault.sh          ← inotifywait auto-reindex daemon
    ├── gen_semantic_links.py   ← Semantic graph → Obsidian wikilinks
    └── setup.sh                ← One-shot installer for fresh machines
```

---

## 4. Every Script — What It Does

### 📄 `scripts/index_vault.py`
The **heart of the pipeline**. Converts raw Markdown into searchable vectors.

**What it does step by step:**
1. Walks all `.md` files recursively (skips `.indexes`, `.git`, `embeddings`, `__pycache__`)
2. Reads each file as UTF-8 text
3. Strips YAML frontmatter (the `---` block at the top)
4. Chunks the body into **200-word windows with 20-word overlap** between chunks
5. Generates a **stable SHA-256 chunk ID** = `sha256(source::chunk_index::first_64_chars)[:32]`
6. Checks if that ID already exists in ChromaDB → **skips if unchanged** (incremental indexing)
7. Sends new chunks to Ollama: `ollama.embeddings(model="mxbai-embed-large", prompt=chunk_text)`
8. Gets back a `[1024 floats]` vector
9. Upserts into ChromaDB collection `second_brain` with metadata: `{source, chunk_index, word_count}`

**Key settings (editable at top of file):**
```python
CHUNK_WORDS    = 200    # words per chunk
CHUNK_OVERLAP  = 20     # words shared between consecutive chunks
EMBED_MODEL    = "mxbai-embed-large"
COLLECTION     = "second_brain"
```

**Usage:**
```bash
python3 ~/Second-Brain/scripts/index_vault.py
```

---

### 📄 `scripts/retrieve.py`
**Semantic search CLI.** Convert a query to a vector, find the most similar chunks.

**What it does:**
1. Takes your query string from command line
2. Embeds it with the same model: `ollama.embeddings(model="mxbai-embed-large", prompt=query)`
3. Queries ChromaDB: `collection.query(query_embeddings=[vec], n_results=top_k, include=[...])`
4. Returns top-K chunks sorted by **cosine similarity** (higher = more relevant)
5. Displays: source file, chunk number, similarity score (0–1), 400-char preview

**Usage:**
```bash
python3 ~/Second-Brain/scripts/retrieve.py "your question here"
python3 ~/Second-Brain/scripts/retrieve.py "ollama setup commands" --top 10
```

**Example output:**
```
Querying 12 chunks for: "how does the second brain work"

[1] 02-Knowledge/Second-Brain-Architecture.md  (chunk #0)  similarity=0.679
    The Second Brain is a local-first semantic knowledge system...

[2] 00-Core/system-prompt.md  (chunk #0)  similarity=0.660
    You are an intelligent assistant with access to a local knowledge base...
```

---

### 📄 `scripts/watch_vault.sh`
**Auto-reindex daemon.** Watches for file changes and triggers re-indexing.

**What it does:**
1. Uses `inotifywait --recursive --monitor` on `~/Second-Brain/`
2. Listens for `close_write` and `moved_to` events on `*.md` files only
3. When a `.md` file is saved → waits **3-second debounce** → runs `index_vault.py`
4. Debounce prevents hammering Ollama on rapid successive saves (e.g. autosave in Obsidian)

**Usage:**
```bash
bash ~/Second-Brain/scripts/watch_vault.sh
# Leave running in background terminal — Ctrl+C to stop
```

> ⚠️ Requires `sudo apt install inotify-tools` (needs sudo in a terminal)

---

### 📄 `scripts/gen_semantic_links.py`
**Graph bridge.** Makes ChromaDB's invisible semantic connections visible in Obsidian.

**What it does:**
1. Loads all chunk embeddings from ChromaDB
2. Averages all chunks per file → one representative 1024-dim vector per note
3. Computes **pairwise cosine similarity** between all files
4. Edges above a configurable threshold (default: 0.70) become `[[wikilinks]]`
5. Injects `related:` frontmatter field into each `.md` file
6. Obsidian Graph View immediately picks up the new links

**Current graph (similarity ≥ 0.60):**
```
system-prompt ────── 0.818 ──── Second-Brain-Architecture
system-prompt ────── 0.778 ──── MCP-Setup
Ollama-Setup  ────── 0.794 ──── Second-Brain-Architecture
Ollama-Setup  ────── 0.703 ──── system-prompt
MCP-Setup     ────── 0.691 ──── Second-Brain-Architecture
MCP-Setup     ────── 0.655 ──── Ollama-Setup
Templates     ────── 0.713 ──── system-prompt
Templates     ────── 0.711 ──── Second-Brain-Architecture
```

**Usage:**
```bash
python3 ~/Second-Brain/scripts/gen_semantic_links.py              # apply links
python3 ~/Second-Brain/scripts/gen_semantic_links.py --dry-run    # preview only
python3 ~/Second-Brain/scripts/gen_semantic_links.py --threshold 0.75  # stricter
python3 ~/Second-Brain/scripts/gen_semantic_links.py --top 8      # more links/note
```

---

### 📄 `scripts/setup.sh`
**One-shot installer.** Run once on a fresh machine.

**What it does (in order):**
1. Checks for `inotify-tools` → installs if missing
2. Checks for `chromadb`, `ollama`, `chroma-mcp` → installs if missing
3. Starts Ollama if not running
4. Checks for `mxbai-embed-large` → pulls if missing (~670 MB)
5. Configures `~/.config/systemd/user/ollama.service` → enabled on login
6. Runs initial `index_vault.py`

```bash
bash ~/Second-Brain/scripts/setup.sh
```

---

## 5. The Complete Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                     WRITE PATH (Indexing)                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  You type a note in Obsidian / any editor                           │
│          │                                                           │
│          ▼ save .md file                                             │
│  ┌───────────────────┐   detects change                             │
│  │  watch_vault.sh   │ ────────────────► waits 3s debounce         │
│  │  (inotifywait)    │                        │                     │
│  └───────────────────┘                        ▼ runs               │
│                                    ┌─────────────────────┐          │
│                                    │   index_vault.py    │          │
│                                    │                     │          │
│                                    │ 1. Walk .md files   │          │
│                                    │ 2. Strip frontmatter│          │
│                                    │ 3. Chunk (200 words)│          │
│                                    │ 4. Hash chunk ID    │          │
│                                    │ 5. Skip if exists   │          │
│                                    └──────────┬──────────┘          │
│                                               │ new chunks          │
│                                               ▼                     │
│                                    ┌─────────────────────┐          │
│                                    │  Ollama :11434      │          │
│                                    │  mxbai-embed-large  │          │
│                                    │  text → [1024 floats]│         │
│                                    └──────────┬──────────┘          │
│                                               │ vectors             │
│                                               ▼                     │
│                                    ┌─────────────────────┐          │
│                                    │  ChromaDB           │          │
│                                    │  .indexes/chroma/   │          │
│                                    │  collection:        │          │
│                                    │  "second_brain"     │          │
│                                    │  hnsw:space=cosine  │          │
│                                    └─────────────────────┘          │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                     READ PATH (Querying)                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  You ask Claude: "How did I set up Ollama?"                         │
│          │                                                           │
│          ▼                                                           │
│  ┌───────────────────┐   MCP stdio   ┌──────────────────────┐       │
│  │  Claude Desktop   │ ────────────► │  chroma-mcp server   │       │
│  │                   │               │  /home/ab/.local/    │       │
│  │                   │               │  bin/chroma-mcp      │       │
│  └───────────────────┘               └──────────┬───────────┘       │
│          ▲                                      │ query             │
│          │                                      ▼                   │
│          │                           ┌──────────────────────┐       │
│          │                           │  ChromaDB            │       │
│          │                           │  cosine search       │       │
│          │                           │  → top-5 chunks      │       │
│          │                           └──────────┬───────────┘       │
│          │                                      │ results           │
│          └──────────────────────────────────────┘                   │
│                                                                      │
│  Claude synthesizes answer from chunks + cites [[source]]           │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                   GRAPH PATH (Obsidian Visualization)                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ChromaDB vectors → pairwise cosine similarity                      │
│          │                                                           │
│          ▼ gen_semantic_links.py                                     │
│  If similarity ≥ threshold → inject [[wikilink]] in frontmatter     │
│          │                                                           │
│          ▼                                                           │
│  Obsidian Graph View reads [[links]] → shows semantic clusters       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 6. The Vector Math (Simplified)

**Embedding:** `text → [0.231, -0.847, 0.112, ... 1024 numbers]`  
Each number captures a different semantic dimension of the text's meaning.

**Cosine similarity:**
```
similarity(A, B) = (A · B) / (|A| × |B|)   ← ranges from 0 to 1
```

| Score | Meaning |
|---|---|
| `0.80+` | Near-identical concepts |
| `0.65–0.80` | Strongly related topics |
| `0.50–0.65` | Related but different angle |
| `< 0.45` | Discard (threshold in system prompt) |

**Why cosine (not euclidean)?** Cosine measures *angle between vectors*, not raw distance — so a long detailed note and a short note on the same topic score as similar, because they point in the same semantic direction even if one is much longer.

---

## 7. Claude Desktop MCP Configuration

**File:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ollama": {
      "command": "/home/ab/.nvm/versions/node/v24.15.0/bin/npx",
      "args": ["-y", "ollama-mcp-server"],
      "env": {
        "OLLAMA_HOST": "http://127.0.0.1:11434",
        "OLLAMA_MODEL": "gemma4:e2b"
      }
    },
    "filesystem": {
      "command": "...npx...",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/media/lab/..."]
    },
    "desktop-commander": { "..." : "..." },
    "excalidraw": { "..." : "..." },

    "second-brain-chroma": {
      "command": "/home/ab/.local/bin/chroma-mcp",
      "args": [
        "--client-type", "persistent",
        "--data-dir", "/home/ab/Second-Brain/.indexes/chroma"
      ]
    }
  }
}
```

The `second-brain-chroma` server starts as a **child process of Claude Desktop** via stdio — no port, no network, just a pipe. When Claude calls a tool, it writes JSON to stdin of `chroma-mcp`, which queries ChromaDB and writes results to stdout.

---

## 8. Ollama Autostart (systemd)

**File:** `~/.config/systemd/user/ollama.service`

```ini
[Unit]
Description=Ollama AI Model Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/ollama serve
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

```bash
systemctl --user status ollama      # check status
systemctl --user start ollama       # start now
systemctl --user enable ollama      # auto-start on login
journalctl --user -u ollama -f      # live logs
```

> ⚠️ Currently shows `inactive` — the background `ollama serve` process started manually is running but the systemd unit is not activated. Run `systemctl --user start ollama` after each reboot until resolved.

---

## 9. Note Template (Frontmatter Standard)

Every note should start with this frontmatter (from `00-Core/Templates/default.md`):

```yaml
---
title: "Your Note Title"
date: YYYY-MM-DD
tags: [tag1, tag2, tag3]
type: note          # note | project | knowledge | memory | daily
status: draft       # draft | active | archived
area: ""            # Projects | Knowledge | Memory | Context | Daily
related:
  - "[[path/to/related-note]]"
summary: "One sentence summary of this note"
---
```

**Why frontmatter matters:**
- `tags` → powers Obsidian tag search and filtering
- `related` → powers Obsidian Graph View connections
- `summary` → Claude can read this as a quick lookup without loading full chunk
- `type` + `status` → lets you filter `archived` notes from active retrieval in future

---

## 10. The System Prompt (What Claude Is Told)

Claude Desktop is configured with a strict **Retrieval-First Protocol**:

1. **Before answering any question** → run `retrieve.py "<reformulated query>"`
2. **Use only chunks with similarity ≥ 0.45** — discard weaker matches
3. **Never read full `.md` files** — always use retrieve.py (saves context window)
4. **Always cite sources** using `[[path/to/note]]` (chunk #N, similarity 0.XX) format
5. **After solving complex problems** → offer to compress insights into `06-AI-Memory/`

This means Claude's answers about YOUR topics are grounded in YOUR notes, not generic training data.

---

## 11. All Commands Reference

### Daily Workflow
```bash
# Start Ollama (if not running)
ollama serve &

# Start file watcher (auto-reindex on every .md save)
bash ~/Second-Brain/scripts/watch_vault.sh

# Manually re-index everything
python3 ~/Second-Brain/scripts/index_vault.py

# Semantic search from terminal
python3 ~/Second-Brain/scripts/retrieve.py "your query here"
python3 ~/Second-Brain/scripts/retrieve.py "docker networking" --top 10

# Rebuild Obsidian semantic graph links
python3 ~/Second-Brain/scripts/gen_semantic_links.py
python3 ~/Second-Brain/scripts/gen_semantic_links.py --threshold 0.65 --dry-run
```

### System Health
```bash
# Check Ollama is running
ollama list

# Check what's indexed
python3 - << 'EOF'
import chromadb; from pathlib import Path
c = chromadb.PersistentClient(str(Path.home()/"Second-Brain/.indexes/chroma"))
col = c.get_collection("second_brain")
print(f"Chunks: {col.count()}")
EOF

# Check MCP config is valid JSON
python3 -m json.tool ~/.config/Claude/claude_desktop_config.json

# Check semantic links in a note
head -15 ~/Second-Brain/02-Knowledge/Second-Brain-Architecture.md
```

### Setup / Recovery
```bash
# Full setup from scratch
bash ~/Second-Brain/scripts/setup.sh

# Start Ollama systemd service
systemctl --user start ollama
systemctl --user enable ollama

# Install missing system dep
sudo apt install inotify-tools

# Reinstall Python packages
pip3 install --user --break-system-packages chromadb ollama chroma-mcp
```

---

## 12. Semantic Graph — Current Connections

```
                    [system-prompt]
                    /      |      \
                0.818   0.778   0.713
                /          \       \
[Second-Brain-Arch]   [MCP-Setup]  [Templates]
         |    \           /
       0.794  0.711    0.655
         |       \    /
   [Ollama-Setup] (0.711 arch-templates)
```

All 5 notes are fully connected in the graph with semantic relationships.

---

## 13. What's Missing / Next Steps

| Feature | Status | How to Add |
|---|---|---|
| `inotify-tools` | ⚠️ Needs `sudo apt install` | Run in terminal with sudo |
| Ollama systemd autostart | ⚠️ Service enabled but needs activation | `systemctl --user start ollama` |
| More notes in vault | 🔲 Only 5 notes indexed | Start writing daily notes |
| `06-AI-Memory/` populated | 🔲 Empty | Ask Claude to distill insights there |
| `05-Daily/` journals | 🔲 Empty | Create `05-Daily/2026-05-08.md` today |
| `01-Projects/` content | 🔲 Empty | Add your active projects |
| Karpathy-style AI compiler | 🔲 Not built yet | AI agent that reads raw input → writes wiki pages |
| Git version control | 🔲 Not initialized | `git init ~/Second-Brain && git add .` |

---

## 14. The Tech Stack — Full Version

```
Layer 0 — Storage:       Markdown (.md) files + Git
Layer 1 — Editor:        Obsidian (local, no sync needed)
Layer 2 — Chunking:      index_vault.py (200-word windows, 20-word overlap)
Layer 3 — Embedding:     mxbai-embed-large via Ollama (1024-dim, cosine)
Layer 4 — Vector DB:     ChromaDB 1.5.9 (persistent, SQLite + HNSW)
Layer 5 — MCP Bridge:    chroma-mcp 0.2.6 (FastMCP, stdio transport)
Layer 6 — LLM:           Claude Desktop (system prompt = retrieval-first protocol)
Layer 7 — Graph:         Obsidian Graph View (fed by gen_semantic_links.py)
Layer 8 — Automation:    watch_vault.sh (inotifywait + debounce)
Layer 9 — Systemd:       ~/.config/systemd/user/ollama.service
```

---

_Last updated: 2026-05-08 | System version: 1.0_
