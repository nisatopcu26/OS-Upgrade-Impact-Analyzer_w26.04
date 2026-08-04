"""Merkezi ayarlar: TTL, model adları, RAG parametreleri.

.env dosyasından okunan değerler burada tek noktada toplanır.
"""

import os

# --- Freshness / cache (M3.5) ---
TTL_DAYS = int(os.getenv("TTL_DAYS", "7"))

# --- RAG (M3) ---
CHROMA_DIR = os.getenv("CHROMA_DIR", "data/chroma")
# Varsayılan S2'de flip edildi (2026-07-29): araştırma kararı bge-small
# (50-soru seti + holdout; update_plan_3). Geri dönüş tek env satırı:
# EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2 (+ eşik 0.30).
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# Model profili (S1 / update_plan_3): koleksiyon adı + sorgu öneki modeli İZLER.
# Tek env satırı (EMBEDDING_MODEL) model+indeks+önek üçünü birlikte değiştirir —
# "geri dönüş tek satırdır" sözünün mekanik karşılığı. bge sorgu önekinin
# SONDAKİ BOŞLUĞU dahildir (rag_layer_bench/bench_embeddings.py ile birebir);
# doküman öneki her iki modelde de boş.
_PROFILES = {
    "sentence-transformers/all-MiniLM-L6-v2": {
        "collection": "ubuntu_minilm",
        "query_prefix": "",
    },
    "BAAI/bge-small-en-v1.5": {
        "collection": "ubuntu_bge",
        "query_prefix": "Represent this sentence for searching relevant passages: ",
    },
}
if EMBEDDING_MODEL not in _PROFILES:
    # Sessiz fallback yok (proje sözleşmesi): bilinmeyen model yanlış indekste
    # öneksiz arama yapardı — açık hata, sessiz bozulmadan iyidir.
    raise ValueError(
        f"Bilinmeyen embedding modeli: {EMBEDDING_MODEL!r} — "
        "config/settings.py'deki _PROFILES tablosuna koleksiyon adı + "
        "sorgu öneki eklenmeli."
    )
# CHROMA_COLLECTION override'ı yalnız test/deney için — ana yol profil türetmesi.
_profile_collection = _PROFILES[EMBEDDING_MODEL]["collection"]
COLLECTION = os.getenv("CHROMA_COLLECTION") or _profile_collection
if COLLECTION != _profile_collection:
    print(f"[WARN] CHROMA_COLLECTION override aktif: '{COLLECTION}' != "
          f"profil koleksiyonu '{_profile_collection}' (model: {EMBEDDING_MODEL})")
QUERY_PREFIX = _PROFILES[EMBEDDING_MODEL]["query_prefix"]
# Chunk sınırlarını belirleyen tokenizer SABİT (V0 chunking): model değişse de
# 328 chunk ve id'leri bayt-bayt aynı kalır (adil kıyas + chunk_id atıflarının
# geçerliliği; kilitli karar #5'in devamı).
CHUNK_TOKENIZER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

TOP_K = int(os.getenv("TOP_K", "5"))
# Benzerlik eşiği (M5 grounding, low_support kapısı) — S2'de bge için yeniden
# kalibre edildi (R4 yöntemi, calibrate_threshold.py): önekli modda alakalı-min
# 0.629 / saçma-maks 0.572 → boşluğun ortası 0.60. (MiniLM'e dönüşte 0.30 —
# o ölçeğin R4 boşluğu [0.331, 0.408] idi.) Altı "alakalı kaynak yok" sayılır.
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.60"))

# --- LLM (M4) ---
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# --- API (M6) ---
# Not: 8000 bu makinede başka bir yerel projeye ait (PHP) — 8010 kullanıyoruz.
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8010")
