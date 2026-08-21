"""Cok parcali bolumlerde 'kisa chunk / baslik seyrelme' onyargisi tekrarlaniyor mu?"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rag.vector_store import search

probes = json.loads(Path("data/eval/multi_chunk_probe.json").read_text())

for p in probes:
    hits = search(p["question"], top_k=10, version="26.04")
    hit_ids = [h["id"] for h in hits]
    target = p["chunk_id"]
    rank = hit_ids.index(target) + 1 if target in hit_ids else None
    top1 = hits[0]["id"]
    top1_sim = hits[0]["similarity"]
    target_sim = next((h["similarity"] for h in hits if h["id"] == target), None)

    status = "OK (rank 1)" if rank == 1 else f"KAYIP (rank={rank})" if rank else "TOP-10 DISI"
    print(f"\n[{status}] {p['question']}")
    print(f"  hedef: {target}  (sim={target_sim})")
    print(f"  top1:  {top1}  (sim={top1_sim})")
