"""M3 / Sprint R3-R4 — Chroma vector store + retrieval.

- PersistentClient: diske yazar (data/chroma), süreç kapansa da index kalır.
- cosine metriği: embedding'ler normalize olduğu için doğal seçim.
- upsert + deterministik id: build_index tekrar koşulunca mükerrer kayıt oluşmaz.
- build_index(): tüm processed JSON'ları chunk'layıp indeksleyen orkestrasyon —
  pipeline'ın "veriyi aranabilir yap" tek komutu.
- search(): sorguyu AYNI modelle embed'leyip en alakalı chunk'ları döner (RAG'in R'si).
"""

import json
from pathlib import Path

import chromadb

from config.settings import (
    CHROMA_DIR, CHUNK_TOKENIZER_MODEL, COLLECTION, EMBEDDING_MODEL,
    QUERY_PREFIX, TOP_K,
)
from src.rag.chunking import Chunk, chunk_release_notes
from src.rag.embeddings import count_tokens, embed_texts

PROCESSED_DIR = Path("data/processed")
# Koleksiyon adı modeli izler (settings profil tablosu, S1): MiniLM →
# 'ubuntu_minilm', bge-small → 'ubuntu_bge'. Literal ad burada YAŞAMAZ.
DEFAULT_COLLECTION = COLLECTION

_client = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
    return _client


def get_collection(name: str = DEFAULT_COLLECTION):
    return get_client().get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def _sanitize(metadata: dict) -> dict:
    """Chroma metadata'sı yalnızca str/int/float/bool kabul eder; None → ''."""
    return {k: ("" if v is None else v) for k, v in metadata.items()}


def index_chunks(chunks: list[Chunk], embeddings,
                 collection_name: str = DEFAULT_COLLECTION) -> None:
    """Chunk + vektörleri Chroma'ya upsert'ler (varsa günceller, yoksa ekler)."""
    if not chunks:
        return
    col = get_collection(collection_name)
    col.upsert(
        ids=[c.id for c in chunks],
        embeddings=[e.tolist() for e in embeddings],
        documents=[c.text for c in chunks],
        metadatas=[_sanitize(c.metadata) for c in chunks],
    )


def build_index(versions: list[str] | None = None,
                collection_name: str = DEFAULT_COLLECTION,
                model_name: str = EMBEDDING_MODEL,
                chunk_model_name: str = CHUNK_TOKENIZER_MODEL) -> dict:
    """Orkestrasyon: processed JSON'ları oku → chunk'la → embed'le → indeksle.

    versions=None ise data/processed altındaki TÜM sürümler işlenir.
    chunk_model_name varsayılanı SABİT (settings.CHUNK_TOKENIZER_MODEL =
    MiniLM): embedding modeli değişse de chunk sınırları/id'leri bayt-bayt
    aynı kalır — adil kıyas (R5) + eski chunk_id atıflarının geçerliliği
    (kilitli karar #5; S1'de EMBEDDING_MODEL varsayılanından ayrıştırıldı,
    yoksa model değişimi sınırları sessizce kaydırırdı).
    Sürüm başına chunk sayısını döner (gözle doğrulama için).
    """
    if versions is None:
        versions = sorted(p.stem for p in PROCESSED_DIR.glob("*.json"))

    counter = lambda t: count_tokens(t, chunk_model_name)
    stats = {}
    for version in versions:
        path = PROCESSED_DIR / f"{version}.json"
        if not path.exists():
            print(f"[WARN] {version}: processed JSON yok, atlandı ({path})")
            continue

        envelope = json.loads(path.read_text(encoding="utf-8"))
        chunks = chunk_release_notes(envelope, counter)
        embeddings = embed_texts([c.text for c in chunks], model_name)
        index_chunks(chunks, embeddings, collection_name)

        stats[version] = len(chunks)
        print(f"[INDEX] {version}: {len(chunks)} chunk → '{collection_name}'")

    total = get_collection(collection_name).count()
    print(f"[INDEX] toplam kayıt: {total}")
    return stats


def search(query: str, top_k: int = TOP_K, version: str | None = None,
           collection_name: str = DEFAULT_COLLECTION,
           model_name: str = EMBEDDING_MODEL,
           query_prefix: str = QUERY_PREFIX) -> list[dict]:
    """Soruya anlamca en yakın chunk'ları döner.

    - Sorgu, chunk'larla AYNI modelle embed edilir (vektör uzayı tutarlılığı).
    - version verilirse metadata filtresi uygulanır (örn. sadece 24.04 chunk'ları).
    - query_prefix varsayılanı profilden gelir (settings.QUERY_PREFIX, S1):
      bge'de önek OTOMATİK uygulanır — R5'te parametre vardı ama hiçbir çağıran
      geçmiyordu, öneksiz bge ölçülen kazancı üretmez. Deney için parametreyle
      ezilebilir.
    - similarity = 1 - cosine_distance (büyük = alakalı).
    """
    q_vec = embed_texts([query_prefix + query], model_name)[0]
    res = get_collection(collection_name).query(
        query_embeddings=[q_vec.tolist()],
        n_results=top_k,
        where={"version": version} if version else None,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0],
                                    res["metadatas"][0], res["distances"][0]):
        hits.append({
            "id": cid,
            "text": doc,
            "metadata": meta,
            "similarity": round(1.0 - dist, 4),
        })
    return hits


if __name__ == "__main__":
    build_index()
