"""Zincir upgrade — Aşama 2 / Sprint 3: kaynağa dayalı envanter evrimi.

Her bacağın envanteri ayrı modellenir: taban envanter kaynak makineden BİR KEZ
okunur; bacak k'ya girerken, önceki bacakların release-notes'ta AÇIKÇA belirtilen
kaldırmaları uygulanmış haliyle kullanılır. Dönüşümler TAHMİN EDİLMEZ,
release notes'tan TÜRETİLİR ve her biri chunk_id + birebir alıntı kanıtı taşır
("uydurma yok" ilkesinin envanter yüzü).

Kaldırma tespiti BİLİNÇLİ dar (D4 + gerçek-veri kalibrasyonu):
- Paket adının HEMEN ARDINDAN (≤50 karakter, virgül/nokta penceyi keser) katı
  bir pasif kaldırma kalıbı gelmeli: "has/have been removed", "was/were
  removed", "is/are no longer available" — ya da "removal of <paket>" biçimi.
- Aynı cümlede geçmek YETMEZ. Gerçek 20.04 verisiyle kanıtlandı (ilk REPL
  koşusunda iki yanlış pozitif): (1) "Since nginx-core dropped the dependency
  ... libnginx-mod-http-geoip can be removed" — kalkan şey bağımlılık, nginx
  değil; (2) "legacy python ... might be removed ... being replaced by the
  python2 ... packages" — python2 kaldırılan değil, YERİNE GELEN paket.
- HARİÇ: "deprecated" (kaldırılmış demek değil — Python 2.7, 20.04'te
  universe'e taşındı ama kurulabilir kaldı), "no longer supported" (destek ≠
  yokluk), geniş-zaman "removes" ("Pacemaker 2.0 removes deprecated syntax" —
  kalkan sözdizimi, paket değil), spekülatif "might/can be removed".
- Kalibrasyon: Sprint 6'da gerçek VM upgrade'ine karşı ölçülür.

Yeniden adlandırma (rename) v1'de YOK (D5): release notes rename'i parse
edilebilir biçimde vermez; çıkarım = uydurma riski. `renamed` alanı hep boş
döner — belgeli sınır (architecture.md).

Bilinen sınır (rapora da yazılır): bu bir MODEL, kesin gerçek değil — release
notes'ta yazmayan bir paket değişikliği modelde görünmez. Kesin gerçek ancak
makine gerçekten upgrade edilip yeniden okunarak bilinir.
"""

import re

from src.rag.chunking import split_sentences

# Ucuz cümle ön-eleme: bu kalıplar yoksa cümle hiç incelenmez
_SENTENCE_GATE = re.compile(
    r"\bremoved\b|\bno longer available\b|\bremoval\s+of\b")

# Katı pasif kaldırma kalıpları — paket adının ardındaki pencerede aranır.
# Pencere [^.;,]{0,50}: virgül/noktalı virgül/nokta özne değişimini işaret
# eder, pencereyi keser. "might/can be removed" bilinçli DIŞARIDA (spekülatif).
_REMOVAL_TAIL = (r"[^.;,]{0,50}?\b(?:(?:has|have)\s+been|was|were)\s+removed\b"
                 r"|[^.;,]{0,50}?\b(?:is|are)\s+no\s+longer\s+available\b")

_MIN_PKG_LEN = 3   # node_package_intersect ile aynı guard: "go" gibi 2 harfli
                   # adlar her metinde eşleşir, gürültü üretir


def _removal_evidence(pkg: str, sentence_low: str) -> bool:
    """Paket bu cümlede AÇIKÇA kaldırılıyor mu? (özne-bitişiklik kuralı)

    Sınır semantiği grounding motoruyla AYNI (solda harf/rakam yok, sağda harf
    yok ama rakam serbest → apache↔apache2, php≠phpmyadmin). Motor burada
    inline kopyalanır çünkü bitişiklik penceresi paket adıyla kaldırma kalıbını
    TEK regex'te ister; parite test_php_phpmyadmin_substring_trap ile korunur.
    """
    p = rf"(?<![a-z0-9]){re.escape(pkg)}(?![a-z])"
    if re.search(rf"{p}(?:{_REMOVAL_TAIL})", sentence_low):
        return True
    # nominal biçim: "the removal of <paket>"
    return re.search(rf"\bremoval\s+of\b[^.;,]{{0,40}}?{p}", sentence_low) is not None


def _default_corpus(version: str) -> list[dict]:
    """Chroma'dan sürümün TÜM chunk'ları: [{"id", "text"}].

    Lazy import (grounding.corpus_vocab_for deseni) — testler Chroma'sız
    sahte korpus enjekte eder.
    """
    from src.rag.vector_store import get_collection
    res = get_collection().get(where={"version": version},
                               include=["documents"])
    return [{"id": i, "text": d} for i, d in zip(res["ids"], res["documents"])]


def find_removed_packages(inventory: set[str] | list[str],
                          corpus: list[dict]) -> list[dict]:
    """Korpusta AÇIKÇA 'kaldırıldı' denen kurulu paketler — kanıtlarıyla.

    Dönüş: [{"package", "chunk_id", "quote"}] (paket adına göre sıralı,
    paket başına İLK kanıt — deterministik: korpus sırası + sorted paketler).
    """
    packages = sorted(p for p in set(inventory) if len(p) >= _MIN_PKG_LEN)
    found: dict[str, dict] = {}
    for chunk in corpus:
        for sentence in split_sentences(chunk["text"]):
            low = sentence.lower()
            if not _SENTENCE_GATE.search(low):
                continue
            for pkg in packages:
                if pkg not in found and _removal_evidence(pkg.lower(), low):
                    found[pkg] = {"package": pkg, "chunk_id": chunk["id"],
                                  "quote": sentence.strip()[:300]}
    return [found[p] for p in sorted(found)]


def evolve_inventory(base_inventory: list[str], legs: list[tuple[str, str]],
                     corpus_fn=None) -> dict:
    """Her bacak için o bacağa GİREN envanteri hesaplar.

    per_leg[(f,t)] = bacağa giren envanter (o bacağın kaldırmaları
    UYGULANMADAN önce — kaldırma SONRAKİ bacaktan itibaren etkili).
    Boş korpus → değişiklik yok, çökme yok.

    Dönüş: {"per_leg": {(f,t): [paketler]},
            "evolution": {(f,t): {"removed": [kanıtlar], "renamed": []}}}
    """
    corpus_fn = corpus_fn or _default_corpus
    per_leg: dict = {}
    evolution: dict = {}
    current = set(base_inventory)
    for from_v, to_v in legs:
        per_leg[(from_v, to_v)] = sorted(current)
        removed = find_removed_packages(current, corpus_fn(to_v))
        evolution[(from_v, to_v)] = {"removed": removed, "renamed": []}
        current -= {r["package"] for r in removed}
    return {"per_leg": per_leg, "evolution": evolution}
