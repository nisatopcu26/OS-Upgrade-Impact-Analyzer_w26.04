"""Part 4 — 26.04 golden set üzerinde retrieval değerlendirmesi.

recall@1, recall@5, MRR — genel + lexical/semantic kırılımı.
Yöntem PDF'teki Bölüm 13'e sadık: sürüm-filtreli arama, aynı search() fonksiyonu.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rag.vector_store import search

GOLDEN_SET_PATH = "data/eval/golden_set_26_04.json"
TOP_K_EVAL = 10  # top-5 recall + rank bilgisi için yeterli marj

def evaluate():
    golden_set = json.loads(Path(GOLDEN_SET_PATH).read_text())
    results = []

    for item in golden_set:
        hits = search(item["question"], top_k=TOP_K_EVAL, version="26.04")
        hit_ids = [h["id"] for h in hits]
        target = item["answer_chunk_id"]

        if target in hit_ids:
            rank = hit_ids.index(target) + 1
        else:
            rank = None

        results.append({
            "question": item["question"],
            "class": item["class"],
            "target": target,
            "rank": rank,
            "top1_id": hit_ids[0] if hit_ids else None,
            "top1_similarity": hits[0]["similarity"] if hits else None,
        })

    return results


def summarize(results, label):
    n = len(results)
    if n == 0:
        return
    recall_at_1 = sum(1 for r in results if r["rank"] == 1) / n
    recall_at_5 = sum(1 for r in results if r["rank"] is not None and r["rank"] <= 5) / n
    mrr = sum((1.0 / r["rank"]) if r["rank"] else 0.0 for r in results) / n

    print(f"\n=== {label} (n={n}) ===")
    print(f"recall@1: {recall_at_1:.3f}")
    print(f"recall@5: {recall_at_5:.3f}")
    print(f"MRR:      {mrr:.3f}")

    misses = [r for r in results if r["rank"] is None or r["rank"] > 5]
    if misses:
        print(f"\n  top-5 dışı kalanlar ({len(misses)}):")
        for m in misses:
            print(f"   - [{m['class']}] {m['question'][:70]}")
            print(f"     hedef: {m['target']}  bulunan_rank: {m['rank']}  top1: {m['top1_id']}")


if __name__ == "__main__":
    results = evaluate()

    Path("data/eval/eval_results_26_04.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2)
    )

    summarize(results, "GENEL")
    summarize([r for r in results if r["class"] == "lexical"], "LEXICAL")
    summarize([r for r in results if r["class"] == "semantic"], "SEMANTIC")

    print(f"\nDetaylı sonuçlar: data/eval/eval_results_26_04.json")
