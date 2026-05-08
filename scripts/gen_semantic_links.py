#!/usr/bin/env python3
"""
gen_semantic_links.py - Build visible graph connections in Obsidian
by injecting [[wikilinks]] based on ChromaDB semantic similarity.

How it works:
  For each note, query ChromaDB for its most similar neighbours.
  If similarity > THRESHOLD, inject a [[wikilink]] into the note's
  frontmatter `related:` field — making it visible in Obsidian Graph View.

Usage:
  python3 ~/Second-Brain/scripts/gen_semantic_links.py
  python3 ~/Second-Brain/scripts/gen_semantic_links.py --threshold 0.75 --dry-run
"""

import argparse
import re
from pathlib import Path
from collections import defaultdict

import chromadb

# ── Config ──────────────────────────────────────────────────────────────────
VAULT_DIR   = Path.home() / "Second-Brain"
CHROMA_DIR  = VAULT_DIR / ".indexes" / "chroma"
COLLECTION  = "second_brain"
THRESHOLD   = 0.70   # cosine similarity threshold (0–1); lower = more links
TOP_K       = 5      # max neighbours to consider per note
SKIP_DIRS   = {".indexes", ".git", "embeddings", "__pycache__"}
# ────────────────────────────────────────────────────────────────────────────


def get_per_file_embeddings(col) -> dict:
    """Average all chunk embeddings for a file into one representative vector."""
    result = col.get(include=["embeddings", "metadatas"])
    file_vecs = defaultdict(list)
    for emb, meta in zip(result["embeddings"], result["metadatas"]):
        file_vecs[meta["source"]].append(emb)

    averaged = {}
    for source, vecs in file_vecs.items():
        n = len(vecs)
        dim = len(vecs[0])
        avg = [sum(vecs[j][i] for j in range(n)) / n for i in range(dim)]
        averaged[source] = avg
    return averaged


def cosine_similarity(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def parse_frontmatter(content: str) -> tuple[dict, str, str]:
    """Return (meta_lines_dict, frontmatter_block, body)."""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            fm = content[3:end]
            body = content[end + 3:]
            return fm, body
    return "", content


def inject_related(md_path: Path, links: list[str], dry_run: bool) -> bool:
    """
    Add wikilinks to the `related:` frontmatter field.
    Returns True if the file was modified.
    """
    content = md_path.read_text(encoding="utf-8", errors="ignore")
    fm, body = parse_frontmatter(content)

    if not fm:
        # No frontmatter — prepend a minimal one
        new_fm = "---\nrelated:\n"
        for lnk in links:
            new_fm += f'  - "[[{lnk}]]"\n'
        new_fm += "---\n"
        new_content = new_fm + content
    else:
        # Parse existing related field
        existing_links = set()
        related_match = re.search(r'^related:\s*\[([^\]]*)\]', fm, re.MULTILINE)
        related_list_match = re.search(r'^related:((?:\n  - .+)+)', fm, re.MULTILINE)

        if related_match:
            for item in related_match.group(1).split(","):
                item = item.strip().strip('"').strip("'")
                if item:
                    existing_links.add(item)
        elif related_list_match:
            for line in related_list_match.group(1).splitlines():
                item = line.strip().lstrip("- ").strip('"').strip("'")
                if item:
                    existing_links.add(item)

        # Only add new links that don't already exist
        new_links = []
        for lnk in links:
            wikilink = f"[[{lnk}]]"
            if wikilink not in existing_links and lnk not in existing_links:
                new_links.append(wikilink)

        if not new_links:
            return False  # Nothing to add

        # Inject into frontmatter
        if related_match:
            # Inline list style — append
            old_val = related_match.group(0)
            items = [x.strip() for x in related_match.group(1).split(",") if x.strip()]
            items += new_links
            new_val = f'related: [{", ".join(items)}]'
            fm = fm.replace(old_val, new_val, 1)
        elif related_list_match:
            # Multi-line list style — append items
            extra = "".join(f'\n  - "{lnk}"' for lnk in new_links)
            old_block = related_list_match.group(0)
            fm = fm.replace(old_block, old_block + extra, 1)
        else:
            # No related field yet — add it
            fm = fm.rstrip() + "\nrelated:\n"
            for lnk in new_links:
                fm += f'  - "{lnk}"\n'

        new_content = f"---{fm}---{body}"

    if content == new_content:
        return False

    if not dry_run:
        md_path.write_text(new_content, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Generate semantic wiki-links between notes for Obsidian graph view"
    )
    parser.add_argument("--threshold", type=float, default=THRESHOLD,
                        help=f"Cosine similarity threshold (default: {THRESHOLD})")
    parser.add_argument("--top", type=int, default=TOP_K,
                        help=f"Max neighbours per note (default: {TOP_K})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing files")
    args = parser.parse_args()

    if not CHROMA_DIR.exists():
        print("ERROR: Index not found. Run index_vault.py first.")
        return

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        col = client.get_collection(COLLECTION)
    except Exception:
        print("ERROR: Collection not found. Run index_vault.py first.")
        return

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Building semantic link graph...")
    print(f"  Threshold : {args.threshold:.2f}")
    print(f"  Max links : {args.top}")
    print()

    # Step 1: Build per-file averaged embeddings
    print("▶ Computing per-file embeddings...")
    file_vecs = get_per_file_embeddings(col)
    files = list(file_vecs.keys())
    print(f"  {len(files)} files in index\n")

    # Step 2: Pairwise cosine similarity
    print("▶ Computing pairwise similarity...")
    edges = defaultdict(list)  # source → [(similarity, target), ...]
    for i, src in enumerate(files):
        for j, tgt in enumerate(files):
            if i >= j:
                continue
            sim = cosine_similarity(file_vecs[src], file_vecs[tgt])
            if sim >= args.threshold:
                edges[src].append((sim, tgt))
                edges[tgt].append((sim, src))

    # Step 3: Keep top-K neighbours per file
    for src in edges:
        edges[src] = sorted(edges[src], reverse=True)[:args.top]

    # Step 4: Print graph
    print("▶ Semantic graph (edges above threshold):")
    total_edges = 0
    for src in sorted(edges.keys()):
        if edges[src]:
            print(f"  {src}")
            for sim, tgt in edges[src]:
                print(f"    ─── {sim:.3f} ──► {tgt}")
                total_edges += 1
    print(f"\n  Total edges: {total_edges // 2} bidirectional links\n")

    if total_edges == 0:
        print(f"No links above threshold {args.threshold}. Try lowering --threshold.")
        return

    # Step 5: Inject links into notes
    print(f"▶ {'[DRY RUN] ' if args.dry_run else ''}Injecting [[wikilinks]] into notes...")
    modified = 0
    for src, neighbours in edges.items():
        md_path = VAULT_DIR / src
        if not md_path.exists():
            continue
        link_targets = [tgt.replace(".md", "") for _, tgt in neighbours]
        changed = inject_related(md_path, link_targets, dry_run=args.dry_run)
        if changed:
            modified += 1
            action = "would update" if args.dry_run else "updated"
            print(f"  ✓ {action}: {src} → {len(link_targets)} link(s)")

    print(f"\n{'='*50}")
    if args.dry_run:
        print(f"DRY RUN complete. {modified} file(s) would be modified.")
        print("Run without --dry-run to apply changes.")
    else:
        print(f"Done. {modified} file(s) updated with semantic wikilinks.")
        print("Reload Obsidian and open Graph View to see connections.")
    print('='*50)


if __name__ == "__main__":
    main()
