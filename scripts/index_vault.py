#!/usr/bin/env python3
"""
index_vault.py - Recursively indexes all .md files in ~/Second-Brain/
into a local ChromaDB collection using mxbai-embed-large via Ollama.

Usage: python ~/Second-Brain/scripts/index_vault.py
"""

import os
import sys
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime

import chromadb
import ollama

# ── Config ──────────────────────────────────────────────────────────────────
VAULT_DIR      = Path.home() / "Second-Brain"
CHROMA_DIR     = VAULT_DIR / ".indexes" / "chroma"
EMBED_MODEL    = "mxbai-embed-large"
COLLECTION     = "second_brain"
CHUNK_WORDS    = 200          # Safe word budget for mxbai-embed-large (512 tok ctx)
CHUNK_OVERLAP  = 20           # words to overlap between chunks
SKIP_DIRS      = {".indexes", ".git", "embeddings", "__pycache__"}
# ────────────────────────────────────────────────────────────────────────────



def chunk_text(text: str, source_path: str) -> list[dict]:
    """Split text into overlapping word-based chunks."""
    words = text.split()
    chunks = []
    start = 0
    chunk_idx = 0
    while start < len(words):
        end = min(start + CHUNK_WORDS, len(words))
        chunk_words = words[start:end]
        chunk_text_str = " ".join(chunk_words)
        chunks.append({
            "text": chunk_text_str,
            "source": source_path,
            "chunk_index": chunk_idx,
            "word_count": len(chunk_words),
        })
        chunk_idx += 1
        if end == len(words):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def get_embedding(text: str) -> list[float]:
    """Get embedding vector from Ollama."""
    response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]


def chunk_id(source: str, chunk_index: int, text: str) -> str:
    """Stable, unique ID for a chunk."""
    raw = f"{source}::{chunk_index}::{text[:64]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Strip YAML frontmatter and return (meta_dict, body)."""
    meta = {}
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            fm = content[3:end].strip()
            body = content[end + 3:].strip()
            for line in fm.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip().strip('"')
            return meta, body
    return meta, content


def index_vault():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting vault index...")
    print(f"  Vault : {VAULT_DIR}")
    print(f"  Chroma: {CHROMA_DIR}")
    print(f"  Model : {EMBED_MODEL}\n")

    # Init ChromaDB
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    # Find all .md files
    md_files = []
    for root, dirs, files in os.walk(VAULT_DIR):
        # Prune skip dirs in-place
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".md"):
                md_files.append(Path(root) / f)

    print(f"Found {len(md_files)} markdown files.\n")

    total_chunks = 0
    skipped = 0

    for md_path in md_files:
        rel_path = str(md_path.relative_to(VAULT_DIR))
        try:
            content = md_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"  SKIP (read error) {rel_path}: {e}")
            skipped += 1
            continue

        _, body = extract_frontmatter(content)
        if not body.strip():
            skipped += 1
            continue

        chunks = chunk_text(body, rel_path)
        file_chunks = 0

        for chunk in chunks:
            cid = chunk_id(chunk["source"], chunk["chunk_index"], chunk["text"])
            # Skip if already indexed (check by id)
            existing = collection.get(ids=[cid])
            if existing["ids"]:
                file_chunks += 1
                total_chunks += 1
                continue

            try:
                embedding = get_embedding(chunk["text"])
            except Exception as e:
                print(f"  EMBED ERROR {rel_path} chunk {chunk['chunk_index']}: {e}")
                continue

            collection.upsert(
                ids=[cid],
                embeddings=[embedding],
                documents=[chunk["text"]],
                metadatas=[{
                    "source": chunk["source"],
                    "chunk_index": chunk["chunk_index"],
                    "word_count": chunk["word_count"],
                }],
            )
            file_chunks += 1
            total_chunks += 1

        print(f"  ✓ {rel_path} → {file_chunks} chunk(s)")

    print(f"\n{'='*50}")
    print(f"Index complete.")
    print(f"  Files processed : {len(md_files) - skipped}")
    print(f"  Files skipped   : {skipped}")
    print(f"  Total chunks    : {total_chunks}")
    print(f"  Collection size : {collection.count()}")
    print(f"{'='*50}")


if __name__ == "__main__":
    index_vault()
