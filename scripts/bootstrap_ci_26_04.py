"""Part 5 — Bootstrap %95 CI (PDF Bolum 13.1 yontemiyle: 1000 resample, sabit tohum)."""
import json
import random
from pathlib import Path

random.seed(42)

def bootstrap_ci(results, metric_fn, n_resamples=1000):
    n = len(results)
    stats = []
    for _ in range(n_resamples):
        sample = [random.choice(results) for _ in range(n)]
        stats.append(metric_fn(sample))
    stats.sort()
    lo = stats[int(0.025 * n_resamples)]
    hi = stats[int(0.975 * n_resamples)]
    return lo, hi

def mrr(results):
    n = len(results)
    return sum((1.0 / r["rank"]) if r["rank"] else 0.0 for r in results) / n

def recall_at_5(results):
    n = len(results)
    return sum(1 for r in results if r["rank"] is not None and r["rank"] <= 5) / n

def recall_at_1(results):
    n = len(results)
    return sum(1 for r in results if r["rank"] == 1) / n

def report(results, label):
    n = len(results)
    m = mrr(results)
    r5 = recall_at_5(results)
    r1 = recall_at_1(results)
    m_lo, m_hi = bootstrap_ci(results, mrr)
    r5_lo, r5_hi = bootstrap_ci(results, recall_at_5)
    r1_lo, r1_hi = bootstrap_ci(results, recall_at_1)
    print(f"\n=== {label} (n={n}) ===")
    print(f"recall@1: {r1:.3f}  95% CI [{r1_lo:.3f}, {r1_hi:.3f}]")
    print(f"recall@5: {r5:.3f}  95% CI [{r5_lo:.3f}, {r5_hi:.3f}]")
    print(f"MRR:      {m:.3f}  95% CI [{m_lo:.3f}, {m_hi:.3f}]")

if __name__ == "__main__":
    results = json.loads(Path("data/eval/eval_results_26_04.json").read_text())
    report(results, "GENEL")
    report([r for r in results if r["class"] == "lexical"], "LEXICAL")
    report([r for r in results if r["class"] == "semantic"], "SEMANTIC")
