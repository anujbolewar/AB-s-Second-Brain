#!/usr/bin/env python3
"""
retrieve.py - Query the Second Brain ChromaDB index semantically.

Usage:
  python ~/Second-Brain/scripts/retrieve.py "your query here"
  python ~/Second-Brain/scripts/retrieve.py "your query here" --top 10
"""

import sys
import argparse
from pathlib import Path

import chromadb
import ollama

# ── Config ──────────────────────────────────────────────────────────────────
VAULT_DIR   = Path.home() / "Second-Brain"
CHROMA_DIR  = VAULT_DIR / ".indexes" / "chroma"
EMBED_MODEL = "mxbai-embed-large"
COLLECTION  = "second_brain"
PREVIEW_LEN = 400   # characters of chunk to show in preview
# ────────────────────────────────────────────────────────────────────────────


def get_embedding(text: str) -> list[float]:
    response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]


def retrieve(query: str, top_k: int = 5):
    if not CHROMA_DIR.exists():
        print("ERROR: Index not found. Run index_vault.py first.")
        sys.exit(1)

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    try:
        collection = client.get_collection(name=COLLECTION)
    except Exception:
        print("ERROR: Collection 'second_brain' not found. Run index_vault.py first.")
        sys.exit(1)

    count = collection.count()
    if count == 0:
        print("WARNING: Collection is empty. Run index_vault.py to index your vault.")
        sys.exit(0)

    print(f"Querying {count} chunks for: \"{query}\"\n")

    query_embedding = get_embedding(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )

    docs      = results["documents"][0]
    metas     = results["metadatas"][0]
    distances = results["distances"][0]

    if not docs:
        print("No results found.")
        return

    print("=" * 60)
    for rank, (doc, meta, dist) in enumerate(zip(docs, metas, distances), 1):
        source      = meta.get("source", "unknown")
        chunk_idx   = meta.get("chunk_index", 0)
        similarity  = 1 - dist   # cosine distance → similarity
        preview     = doc[:PREVIEW_LEN].replace("\n", " ")
        if len(doc) > PREVIEW_LEN:
            preview += "..."

        print(f"[{rank}] {source}  (chunk #{chunk_idx})  similarity={similarity:.3f}")
        print(f"    {preview}")
        print()

    print("=" * 60)
    print(f"Top {len(docs)} results from {count} indexed chunks.")


def main():
    parser = argparse.ArgumentParser(description="Query your Second Brain")
    parser.add_argument("query", nargs="+", help="Search query (quoted or unquoted)")
    parser.add_argument("--top", "-n", type=int, default=5, help="Number of results (default: 5)")
    args = parser.parse_args()

    query = " ".join(args.query)
    retrieve(query, top_k=args.top)


if __name__ == "__main__":
    main()
