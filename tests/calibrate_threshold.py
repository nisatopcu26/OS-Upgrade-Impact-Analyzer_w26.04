"""S2 (update_plan_3) — benzerlik eşiği kalibrasyon aracı.

R4 yönteminin tekrarı (alakalı/alakasız tepe-skor boşluğu) — ama eşiğin GERÇEK
kullanım yolunda: grounding'in iddia↔atıf-chunk simetrik kosinüsü
(grounding.py Katman 2, `low_support` RED kapısı).

Üç dağılım ölçülür:
  - alakalı   : örnek raporlardaki (accuracy-audit'te elle doğrulanmış SADIK)
                iddialar × kendi atıf chunk'ları → best kosinüs
  - saçma     : alan-dışı uydurma iddialar × tüm chunk havuzu → best kosinüs
                (eşiğin ASIL hedefi — kanonik low_support vakası)
  - karışık   : iddia, BAŞKA sürümlerin chunk'larına karşı → best kosinüs
                (yanlış-atıf sınıfı; kısmen sözcüksel katmanın işi — bağlam
                için raporlanır, eşik seçimine tek başına dayanak yapılmaz)

Açık karar #2 ölçümü: aynı setler iki modda koşulur — iddia embed'i ÖNEKSİZ
(simetrik, mevcut davranış) ve ÖNEKLİ (profilin sorgu öneki; chunk hep öneksiz).
Boşluğu geniş açan mod kazanır.

Kullanım (model env ile seçilir; koleksiyon profili izler):
  .venv/bin/python tests/calibrate_threshold.py                      # MiniLM
  EMBEDDING_MODEL=BAAI/bge-small-en-v1.5 \\
      .venv/bin/python tests/calibrate_threshold.py                  # bge
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import EMBEDDING_MODEL, QUERY_PREFIX, SIMILARITY_THRESHOLD
from src.rag.embeddings import embed_texts
from src.rag.vector_store import get_collection

NONSENSE = [
    "The moon is made of green cheese and tastes great.",
    "Unicorns are now supported natively.",
    "Purple elephants dance in the data center every night.",
    "The stock market closed higher on Tuesday afternoon.",
    "Chocolate cake recipes require three eggs and butter.",
]


def load_claims(paths):
    """(iddia, chunk_id listesi, sürüm) üçlüleri + benzersiz chunk metinleri."""
    col = get_collection()
    claims, chunk_text = [], {}
    for p in paths:
        r = json.loads(Path(p).read_text(encoding="utf-8"))
        for c in r["claims"]:
            ids = c["chunk_ids"]
            got = col.get(ids=ids, include=["documents"])
            for cid, doc in zip(got["ids"], got["documents"]):
                chunk_text[cid] = doc
            claims.append({"text": c["text"], "chunk_ids": ids,
                           "version": r["target_version"]})
    return claims, chunk_text


def stats(scores):
    a = np.array(sorted(scores))
    return (f"min {a.min():.3f} · p10 {np.percentile(a, 10):.3f} · "
            f"medyan {np.median(a):.3f} · p90 {np.percentile(a, 90):.3f} · "
            f"maks {a.max():.3f}")


def run_mode(claims, chunk_text, prefix: str):
    """Bir modda (önekli/öneksiz iddia embed'i) üç dağılımı hesaplar."""
    cids = sorted(chunk_text)
    cid_ix = {c: i for i, c in enumerate(cids)}
    chunk_vecs = embed_texts([chunk_text[c] for c in cids])          # hep öneksiz
    claim_vecs = embed_texts([prefix + c["text"] for c in claims])
    nonsense_vecs = embed_texts([prefix + t for t in NONSENSE])

    sim = claim_vecs @ chunk_vecs.T                                  # normalize → kosinüs

    relevant, shuffled = [], []
    for i, c in enumerate(claims):
        own = [cid_ix[x] for x in c["chunk_ids"]]
        relevant.append(float(sim[i, own].max()))
        other = [j for j, cid in enumerate(cids)
                 if not cid.startswith(c["version"] + "_")]
        if other:
            shuffled.append(float(sim[i, other].max()))

    nonsense = (nonsense_vecs @ chunk_vecs.T).max(axis=1).tolist()
    return relevant, nonsense, shuffled


def main():
    argv = [a for a in sys.argv[1:] if a != "--dump"]
    dump = "--dump" in sys.argv[1:]
    paths = argv or sorted(
        str(p) for p in Path("docs/sample-reports").glob("*.json"))
    claims, chunk_text = load_claims(paths)
    dumped = {}
    print(f"model: {EMBEDDING_MODEL}")
    print(f"iddia: {len(claims)} · benzersiz atıf chunk'ı: {len(chunk_text)} · "
          f"mevcut eşik: {SIMILARITY_THRESHOLD}")

    for label, prefix in (("ÖNEKSİZ (simetrik — mevcut davranış)", ""),
                          ("ÖNEKLİ (profil sorgu öneki)", QUERY_PREFIX)):
        if prefix == "" and label.startswith("ÖNEKLİ"):
            print(f"\n--- {label}: profil öneki boş, mod atlandı ---")
            continue
        rel, non, shuf = run_mode(claims, chunk_text, prefix)
        dumped[label.split(" ")[0]] = {"alakali": rel, "sacma": non, "karisik": shuf}
        gap_lo, gap_hi = max(non), min(rel)
        print(f"\n--- {label} ---")
        print(f"alakalı  ({len(rel):3d}): {stats(rel)}")
        print(f"saçma    ({len(non):3d}): {stats(non)}")
        print(f"karışık  ({len(shuf):3d}): {stats(shuf)}  [bağlam — bkz. docstring]")
        if gap_lo < gap_hi:
            print(f"BOŞLUK: saçma-maks {gap_lo:.3f} < alakalı-min {gap_hi:.3f} → "
                  f"orta nokta ÖNERİ: {(gap_lo + gap_hi) / 2:.2f}")
        else:
            print(f"BOŞLUK YOK: saçma-maks {gap_lo:.3f} >= alakalı-min {gap_hi:.3f} "
                  f"— eşik bu modda güvenle seçilemez (rollback sinyali, plana bak)")

    if dump:
        safe = EMBEDDING_MODEL.split("/")[-1]
        out = Path("docs/s5-matrix") / f"threshold_calib_{safe}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(
            {"model": EMBEDDING_MODEL, "threshold": SIMILARITY_THRESHOLD,
             "modes": dumped}, indent=2, ensure_ascii=False))
        print(f"[✓] ham skorlar: {out}")


if __name__ == "__main__":
    main()
