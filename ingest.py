"""
Ingests every markdown file in docs/ into a persistent ChromaDB collection.

Chunking is intentionally simple (split by blank line / paragraph) since the
docs are short. For real-world docs you'd want a smarter chunker, but simple
chunking keeps this test lab easy to reason about when you're checking which
chunk got retrieved.

Usage:
    python ingest.py
"""

from __future__ import annotations

import glob
import os

import chromadb

DOCS_DIR = "docs"
DB_DIR = "chroma_db"
COLLECTION_NAME = "help_center"

# Keywords that mark a document as no longer authoritative. Checked against
# the first ~300 chars of the doc, where a "superseded" notice would live.
SUPERSEDED_MARKERS = ("superseded", "no longer be used", "outdated", "legacy revision")


def detect_status(text: str) -> str:
    """
    Classify a doc as 'current' or 'superseded' based on a lifecycle note in
    its opening lines. This is what test 3 (conflicting sources) exposed as
    missing: retrieval had no signal that refund-policy-2022-legacy.md was
    stale, so it competed with refund-policy.md on similarity alone.
    """
    head = text[:300].lower()
    if any(marker in head for marker in SUPERSEDED_MARKERS):
        return "superseded"
    return "current"


def chunk_markdown(text: str, source: str) -> list[dict]:
    """Split a markdown doc into paragraph-level chunks."""
    status = detect_status(text)
    raw_chunks = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    for i, chunk in enumerate(raw_chunks):
        # Skip pure headings with nothing else on the line
        if chunk.startswith("#") and len(chunk.split("\n")) == 1 and len(chunk) < 60:
            continue
        chunks.append({
            "id": f"{source}::chunk-{i}",
            "text": chunk,
            "source": source,
            "status": status,
        })
    return chunks


def main():
    client = chromadb.PersistentClient(path=DB_DIR)

    # Fresh collection each run so re-ingesting is idempotent.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    all_chunks = []
    for filepath in sorted(glob.glob(os.path.join(DOCS_DIR, "*.md"))):
        source = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        all_chunks.extend(chunk_markdown(text, source))

    if not all_chunks:
        print("No chunks found — check that docs/*.md exist.")
        return

    collection.add(
        ids=[c["id"] for c in all_chunks],
        documents=[c["text"] for c in all_chunks],
        metadatas=[{"source": c["source"], "status": c["status"]} for c in all_chunks],
    )

    superseded_sources = sorted({c["source"] for c in all_chunks if c["status"] == "superseded"})
    print(f"Ingested {len(all_chunks)} chunks from "
          f"{len(set(c['source'] for c in all_chunks))} documents "
          f"into '{COLLECTION_NAME}' at {DB_DIR}/")
    if superseded_sources:
        print(f"Flagged as superseded (deprioritized at retrieval time): "
              f"{', '.join(superseded_sources)}")


if __name__ == "__main__":
    main()
