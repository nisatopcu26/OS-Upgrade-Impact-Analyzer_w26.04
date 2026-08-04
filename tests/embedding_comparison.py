"""M3 / Sprint R5 — İki embedding modelinin kendi verimizde kıyası.

Metrikler:
- recall@5 (hit rate): doğru chunk ilk 5 sonuçta geldi mi? RAG için en anlamlı
  metrik — LLM'e zaten ilk k chunk veriliyor.
- MRR: doğru chunk kaçıncı sırada geldi (1/sıra ortalaması) — sıralama inceliği.

Adil kıyas: iki collection da AYNI chunk'ları içerir (chunk sınırları MiniLM
tokenizer'ıyla çizildi — bkz. build_index(chunk_model_name)).

bge notu: bge ailesi sorguya önek ister; dokümanlara EKLENMEZ, sadece sorguya.

Altın set: 10 soru, relevant_ids elle işaretlendi (chunk içerikleri keyword
taramasıyla bulunup gözle doğrulandı).

Çalıştır:  .venv/bin/python tests/embedding_comparison.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import _PROFILES
from src.rag.vector_store import search

# Koleksiyon + önek tek kaynaktan (settings._PROFILES, S1) — burada kopya
# tutulmaz ki profil değişince bu script sessizce eskimesin.
MODELS = {
    "minilm": {"model": "sentence-transformers/all-MiniLM-L6-v2",
               **_PROFILES["sentence-transformers/all-MiniLM-L6-v2"]},
    "bge": {"model": "BAAI/bge-small-en-v1.5",
            **_PROFILES["BAAI/bge-small-en-v1.5"]},
}

GOLD = [
    {"q": "Which Linux kernel version ships with Ubuntu 24.04?",
     "version": "24.04", "relevant_ids": ["24.04_linux-kernel_0"]},
    {"q": "What happened to the pptpd package in 24.04?",
     "version": "24.04", "relevant_ids": ["24.04_pptpd-removed_0"]},
    {"q": "Are TLS 1.0 and TLS 1.1 still available?",
     "version": "24.04",
     "relevant_ids": ["24.04_tls-1-0-1-1-and-dtls-1-0-are-forcefully-disabled_0"]},
    {"q": "What is new in the PHP version shipped with Ubuntu 20.04?",
     "version": "20.04", "relevant_ids": ["20.04_PHP_7.4_0"]},
    {"q": "Which systemd version does Ubuntu 24.04 use?",
     "version": "24.04", "relevant_ids": ["24.04_systemd-v255-4_0"]},
    {"q": "Does OpenSSH support U2F FIDO hardware security keys?",
     "version": "20.04",
     "relevant_ids": ["20.04_OpenSSH_updates_with_U2F_Support_0",
                      "20.04_OpenSSH_updates_with_U2F_Support_1"]},
    {"q": "Which PostgreSQL version ships with Ubuntu 20.04?",
     "version": "20.04", "relevant_ids": ["20.04_PostgreSQL_12_0"]},
    {"q": "What replaced ifupdown for network configuration?",
     "version": "18.04", "relevant_ids": ["18.04_New_since_16.04_LTS_0"]},
    {"q": "What known bugs and issues exist in this release?",
     "version": "22.04", "relevant_ids": ["22.04_known-issues_0"]},
    {"q": "What are the known problems with the installer?",
     "version": "24.04", "relevant_ids": ["24.04_installer-and-upgrades_0",
                                          "24.04_installer-and-upgrades_1"]},
]


def evaluate(model_key: str, k: int = 5) -> dict:
    cfg = MODELS[model_key]
    hits, rr_sum, misses = 0, 0.0, []
    for item in GOLD:
        results = search(
            item["q"], top_k=k, version=item["version"],
            collection_name=cfg["collection"], model_name=cfg["model"],
            query_prefix=cfg["query_prefix"],
        )
        returned = [r["id"] for r in results]
        relevant = set(item["relevant_ids"])

        rank = next((i + 1 for i, rid in enumerate(returned) if rid in relevant), None)
        if rank:
            hits += 1
            rr_sum += 1.0 / rank
        else:
            misses.append(item["q"])

    return {
        "recall@k": hits / len(GOLD),
        "mrr": rr_sum / len(GOLD),
        "misses": misses,
    }


if __name__ == "__main__":
    print(f"Altın set: {len(GOLD)} soru | k=5\n")
    print(f"| Model  | recall@5 | MRR  |")
    print(f"|--------|----------|------|")
    results = {}
    for key in MODELS:
        r = evaluate(key)
        results[key] = r
        print(f"| {key:<6} | {r['recall@k']:.2f}     | {r['mrr']:.2f} |")

    for key, r in results.items():
        if r["misses"]:
            print(f"\n{key} kaçırdıkları:")
            for q in r["misses"]:
                print(f"  ✗ {q}")
