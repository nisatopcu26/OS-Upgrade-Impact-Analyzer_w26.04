"""Linux kernel sorusu neden yanlis alt-chunk'a gitti — derin inceleme."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rag.vector_store import search

QUESTION = "What Linux kernel version does Ubuntu 26.04 ship?"
TARGET = "26.04_linux-kernel-7-0-src1_0"

hits = search(QUESTION, top_k=10, version="26.04")

print(f"Soru: {QUESTION}")
print(f"Hedef: {TARGET}\n")
print("Top-10 sonuc:")
for i, h in enumerate(hits, 1):
    marker = " <-- HEDEF" if h["id"] == TARGET else ""
    print(f" {i}. {h['id']}  sim={h['similarity']:.4f}{marker}")

print("\n--- Chunk metinleri (linux-kernel-7-0-src1 ailesi) ---")
chunks = json.loads(Path("data/processed/26.04_chunks_dump.json").read_text())
for c in chunks:
    if c["id"].startswith("26.04_linux-kernel-7-0-src1"):
        print(f"\n[{c['id']}]")
        print(c["text"][:400])
