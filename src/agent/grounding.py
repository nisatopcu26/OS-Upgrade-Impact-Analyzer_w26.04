"""M5 — Grounding: "uydurmama" kuralının mimari garantisi.

LLM'e "sadece kaynaklara dayan" demek yetmez — burada her iddia MEKANİK olarak
doğrulanır (güven ama kontrol et):

1. chunk_ids boş → RED (kaynaksız iddia)
2. Atıf yapılan id, LLM'e verilen bağlamda yok → RED (uydurulmuş atıf;
   Chroma'da olsa bile LLM onu GÖRMEDİYSE dayanak sayılmaz)
3. İddia metni ↔ atıf yapılan chunk benzerliği eşiğin altında → RED
   (kaynak var ama iddiayı desteklemiyor)

RED'lenen iddialar sessizce silinmez: raporda "kaynak bulunamadı" notuna
dönüşür — kullanıcı neyin doğrulanamadığını GÖRÜR.
"""

import re

import numpy as np

from config.settings import LLM_MODEL, QUERY_PREFIX, SIMILARITY_THRESHOLD
from src.agent._common_words import COMMON_WORDS
from src.rag.embeddings import embed_texts

# Her upgrade raporunda doğal olarak geçen, kontrol dışı kelimeler
_ENTITY_STOPLIST = {"ubuntu", "lts", "os"}


def _extract_entities(text: str) -> set[str]:
    """İddiadaki 'teknik varlıkları' çıkarır — kısmi-uydurma yakalamak için.

    Yakalananlar (halüsinasyonun en tehlikeli yüzeyi):
    - sürüm numaraları: 24.04, 6.8, v255.4, 10.x, 2.4.58
    - ayraçlı/rakamlı paket-vari adlar: mod_md, pcre2, apt-mark, python3.10
    - büyük harfli kısaltmalar: GCC, TLS, PHP
    Sınır: düz küçük-harfli özel isimler (ör. 'tailscale') yakalanmaz —
    onlar kosinüs kontrolüne emanet (architecture.md'de belgeli).
    """
    entities = set()
    for tok in re.findall(r"[A-Za-z][\w.+-]*[\w]|[\d]+(?:\.[\w]+)+", text):
        low = tok.lower().strip(".")
        if low in _ENTITY_STOPLIST or len(low) < 2:
            continue
        has_digit = any(ch.isdigit() for ch in tok)
        has_sep = any(ch in "._-" for ch in tok.strip("._-"))
        is_acronym = tok.isupper() and len(tok) >= 2
        if has_digit or has_sep or is_acronym:
            # v2.1 kalibrasyon bulgusu: "long-term" gibi TÜM parçaları yaygın
            # İngilizce olan bileşikler teknik varlık değil (tire varyantı
            # "long term" haksız RED üretiyordu). "security-hardening" kalır:
            # 'hardening' yaygın listede değil — GCC süsleme yakalaması korunur.
            if has_sep and not has_digit and not is_acronym:
                parts = [p for p in re.split(r"[._-]", low) if p]
                if parts and all(p in COMMON_WORDS or p in _ENTITY_STOPLIST
                                 for p in parts):
                    continue
            entities.add(low)
    return entities


# --- Eşleşme motoru (v2.1 / S2) -------------------------------------------
# Substring yerine kelime-sınırlı arama. \b yerine lookaround: varlıklar
# . _ - + içerebiliyor ve \b'nin noktalama etrafındaki davranışı sürprizli.

_VERSION_RE = re.compile(r"^(?:v\.?)?\d+(?:\.[a-z0-9]+)+$")


def _looks_like_version(entity: str) -> bool:
    """'24.04', '6.8', 'v255.4', 'v.24.1.3', '10.x' gibi sürüm-vari mi? (nokta şart)"""
    return bool(_VERSION_RE.match(entity))


def _version_in_text(version: str, text: str) -> bool:
    """Sürüm eşleşmesi — ana-sürüm önek esnekliğiyle.

    İddia '255'   / kaynak '255.4'  → EŞLEŞİR (iddia daha az hassas — sorun değil)
    İddia 'v255.4'/ kaynak '255.4'  → EŞLEŞİR ('v'/'v.' öneki normalize edilir)
    İddia 'v24.1.3'/kaynak 'v.24.1.3' → EŞLEŞİR (Ubuntu'nun 'v.' yazımı —
      2026-07-09 tur bulgusu: sadık cloud-init iddiası haksız RED yiyordu)
    İddia '255.4' / kaynak '255'    → EŞLEŞMEZ (model hassasiyet EKLEMİŞ — S4'te FLAG)
    İddia '6.9'   / kaynak '6.8'    → EŞLEŞMEZ (uydurma sürüm — RED kalır)
    Solda harf serbest ('python3.8' içindeki 3.8 bulunur), rakam/nokta yasak
    ('13.8' içindeki 3.8 bulunmaz).
    """
    v = re.escape(version.lstrip("v."))
    return re.search(rf"(?<![\d.])(?:v\.?)?{v}(?:\.[\w]+)*(?!\w)", text) is not None


def _overprecise_version(version: str, text: str) -> bool:
    """İddia sürümü, kaynaktaki bir sürümün DAHA hassas hali mi?
    (kaynak '6.8', iddia '6.8.4' → True; kaynak '6.8', iddia '6.9' → False)"""
    claimed = version.lstrip("v.")
    for m in re.finditer(r"(?<![\w.])(?:v\.?)?(\d+(?:\.[\w]+)*)(?!\w)", text):
        src = m.group(1)
        if claimed != src and claimed.startswith(src + "."):
            return True
    return False


def _morph_variants(word: str) -> tuple[str, ...]:
    """Basit çekim varyantları (tekil/çoğul + -ing) — stem'leme DEĞİL, bilinçli dar.

    2026-07-09 tur bulgusu: iddia 'stages' (çoğul), kaynak 'stage (PPS)'
    (tekil) → haksız FLAG. Morfoloji farkı uydurma değildir; sağda-rakam
    toleransının (apache↔apache2) morfolojik kardeşi. Kökü değiştiren
    çekimler ('libraries'↔'library') kapsam dışı — bilinen sınır.
    len>3 koşulu kısaltmaları korur ('tls' → 'tl' üretilmez).

    2026-07-10 tur bulgusu (uygulama 2026-07-29): iddia 'bringing', kaynak
    'brings' → haksız FLAG; -ing çekimi de aynı sınıf. Hangi gövdenin doğru
    olduğu mekanik bilinemez → TÜM adaylar üretilir (bringing→bring,
    handling→handle, dropping→drop), yanlış aday korpusta geçmediği için
    zararsızdır. Gövde ≥4 harf koşulu 'string'→'str' gibi kısa gövdeleri
    engeller. -al/-ic türetmeleri ('graphical') kapsam DIŞI — çekim değil
    türetme; o vaka COMMON_WORDS'te çözülür (açık karar #3).

    2026-07-29 E2E tur bulgusu: iddia 'PPTP' (kısaltma), kaynak 'pptpd' →
    sağda-harf sınırı bayrak kaldırma iddiasını haksız RED'liyordu. Unix
    daemon konvansiyonu (protokol+d: sshd/ntpd/dhcpd/pptpd) DAR varyant
    olarak eklendi — yalnız tek 'd' eki/kırpımı; php↔phpmyadmin koruması
    (genel sağda-harf yasağı) aynen durur.
    """
    variants = [word]
    if word.endswith("s") and len(word) > 3:
        variants.append(word[:-1])                      # stages → stage
        if word.endswith("es") and word[:-2].endswith(("s", "x", "z", "ch", "sh")):
            variants.append(word[:-2])                  # patches → patch
    elif not word.endswith("s"):
        variants.append(word + "s")                     # iddia tekil, kaynak çoğul
        if word.endswith(("x", "z", "ch", "sh")):
            variants.append(word + "es")                # patch → patches
    if word.endswith("ing") and len(word) > 5:
        stem = word[:-3]
        stems = [stem, stem + "e"]                      # handling → handl, handle
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            stems.append(stem[:-1])                     # dropping → drop
        for s in stems:
            if len(s) >= 4:                             # 'string' → 'str' üretilmez
                variants += [s, s + "s"]                # kaynak 'brings' da olabilir
    elif not word.endswith("ing") and len(word) >= 4:
        variants.append(word + "ing")                   # port → porting
        if word.endswith("e"):
            variants.append(word[:-1] + "ing")          # handle → handling
        elif word[-1] not in "aeious":
            variants.append(word + word[-1] + "ing")    # drop → dropping
    if not word.endswith("d"):
        variants.append(word + "d")                     # pptp → pptpd (daemon)
    elif len(word) > 3:
        variants.append(word[:-1])                      # sshd → ssh
    return tuple(variants)


def _entity_in_text(entity: str, text: str) -> bool:
    """Varlık, metinde 'kelime olarak' geçiyor mu? (text lowercase verilmeli)

    Sınır kuralı: solda harf/rakam olamaz; sağda HARF olamaz ama RAKAM serbest —
    'apache' ↔ 'apache2', 'php' ↔ 'php8.1' meşru ek-varyantları (S1 verisiyle
    doğrulandı), 'php' ↔ 'phpmyadmin' ise engellenir (sağda harf).
    Çekim farkı tolere edilir ('stages' ↔ 'stage', 'bringing' ↔ 'brings' —
    _morph_variants).
    """
    if _looks_like_version(entity):
        return _version_in_text(entity, text)
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(v)}(?![a-z])", text) is not None
        for v in _morph_variants(entity))


def missing_hard_entities(text: str, source_text: str,
                          allowed: set | tuple = ()) -> list[str]:
    """Sert varlıklardan (rakam/ayraç/kısaltma) kaynakta bulunmayanlar.

    grounding, accuracy_audit ve testlerin ORTAK giriş noktası — eşleşme
    semantiği tek yerde yaşar (v2.1: substring değil, kelime sınırı).
    """
    allowed_low = {t.lower() for t in allowed}
    src = source_text.lower()
    return [e for e in sorted(_extract_entities(text))
            if e not in allowed_low and not _entity_in_text(e, src)]


# --- Yumuşak varlık sınıfı (v2.1 / S3) -------------------------------------
# v2'nin belgeli kör noktası: 'tailscale' gibi düz küçük-harf özel isimler.
# Kanıt gücü düşük (düz kelime), o yüzden karar da kademeli (S4 politikası).

_SOFT_WORD = re.compile(r"\b[a-z]{4,}\b")


def _is_common(word: str) -> bool:
    """Yaygın İngilizce mi? Çekimler de yaygın sayılır — liste kök ağırlıklı
    olduğundan 'stage' listedeyse 'stages', 'bring' listedeyse 'bringing' de
    yaygındır (2026-07-09 'stages' + 2026-07-10 'bringing' tur bulguları:
    ikisi de haksız FLAG üretiyordu)."""
    return any(v in COMMON_WORDS or v in _ENTITY_STOPLIST
               for v in _morph_variants(word))


def _extract_soft_entities(text: str) -> set[str]:
    """Düz küçük-harf terimler (>=4 harf) — yaygın İngilizce dışındakiler.

    NOT: COMMON_WORDS İngilizce; rapor dili İngilizce olduğu sürece geçerli
    (kilitli karar). Rapor dili değişirse bu katman yeniden kalibre edilmeli.
    """
    return {w for w in _SOFT_WORD.findall(text.lower()) if not _is_common(w)}


_corpus_vocab_cache: dict[str, set[str]] = {}


def corpus_vocab_for(version: str) -> set[str]:
    """Hedef sürümün TÜM chunk'larından kelime sözlüğü (sürüm başına bir kez).

    İki seviyeli sinyalin temeli: terim atıfta yok ama korpusta varsa
    'yanlış atıf' (zayıf sinyal → FLAG); korpusun tamamında da yoksa hiçbir
    kaynağa dayanamaz → büyük olasılıkla uydurma (güçlü sinyal → RED).
    """
    if version not in _corpus_vocab_cache:
        # Lazy import: testler Chroma'sız sahte sözlük enjekte edebilsin
        from src.rag.vector_store import get_collection
        docs = get_collection().get(where={"version": version},
                                    include=["documents"])["documents"]
        _corpus_vocab_cache[version] = set(
            re.findall(r"[a-z][\w.+-]*", "\n".join(docs).lower()))
    return _corpus_vocab_cache[version]


def verify_claims(claims: list[dict], context_chunks: list[dict],
                  threshold: float = SIMILARITY_THRESHOLD,
                  allowed_terms: tuple = (),
                  corpus_vocab: set | None = None) -> tuple[list, list]:
    """İddiaları LLM'in gördüğü bağlam chunk'larına karşı doğrular.

    Üç katman (v2.1): (1a) sert sözcüksel — rakamlı/ayraçlı/kısaltma varlıklar
    atıf yapılan chunk'ta var mı (yoksa RED; sürüm sadece fazla-hassassa FLAG);
    (1b) yumuşak sözcüksel — düz küçük-harf terimler atıfta/korpusta var mı
    (korpusta da yoksa RED, sadece atıfta yoksa FLAG); (2) anlamsal — kosinüs
    benzerliği eşiği. Kanıt gücü kademeli olduğu için ceza da kademeli:
    FLAG'li iddia rapora girer ama şüpheli detayı işaretlenir (sessizce silme
    olmadığı gibi sessizce aklama da yok).

    allowed_terms: mevcut/hedef sürüm gibi meşru ama chunk'ta geçmeyebilecek
    terimler. corpus_vocab: hedef sürümün kelime sözlüğü (corpus_vocab_for ile;
    testler Chroma'sız sahte sözlük enjekte edebilir; None → uydurma/yanlış-atıf
    ayrımı yapılamaz, yumuşak eksikler FLAG olur).
    Döner: (verified, rejected) — verified'da flags, rejected'da red gerekçesi.
    """
    by_id = {c["id"]: c for c in context_chunks}
    allowed = {t.lower() for t in allowed_terms}
    verified, rejected = [], []

    for claim in claims:
        text = (claim.get("text") or "").strip()
        chunk_ids = claim.get("chunk_ids") or []

        if not text:
            continue
        if not chunk_ids:
            rejected.append({**claim, "reject_reason": "no_source_cited"})
            continue

        known = [cid for cid in chunk_ids if cid in by_id]
        if not known:
            rejected.append({**claim, "reject_reason": "unknown_chunk_id"})
            continue

        source_text = " ".join(
            by_id[cid]["text"] + " " + by_id[cid]["metadata"].get("section_title", "")
            for cid in known
        ).lower()
        flags = []

        # Katman 1a — SERT sözcüksel (v2.1: kelime-sınırlı motor, substring değil)
        hard_missing = missing_hard_entities(text, source_text, allowed)
        truly_missing = []
        for e in hard_missing:
            if _looks_like_version(e) and _overprecise_version(e, source_text):
                # kaynak '6.8' derken iddia '6.8.4' diyor — uydurma denemez
                # (model yuvarlamış da olabilir) ama detay kaynakta yok → FLAG
                flags.append({"term": e, "reason": "overprecise_version"})
            else:
                truly_missing.append(e)
        if truly_missing:
            rejected.append({**claim, "reject_reason": "unverified_entity",
                             "missing_entities": truly_missing})
            continue

        # Katman 1b — YUMUŞAK sözcüksel: düz küçük-harf terimler
        soft_missing = sorted(
            t for t in _extract_soft_entities(text)
            if t not in allowed and not _entity_in_text(t, source_text))
        if corpus_vocab is not None:
            # Sözlük üyeliği de çekim-toleranslı: korpus 'daemon' derken iddianın
            # 'daemons' demesi uydurma değildir (motorla aynı morfoloji kuralı)
            fabricated = [t for t in soft_missing
                          if not any(v in corpus_vocab
                                     for v in _morph_variants(t))]
            if fabricated:
                # ne atıfta ne korpusta ne yaygın İngilizce → hiçbir kaynağa
                # dayanamaz; uydurma özel isim en tehlikeli sınıf → RED
                rejected.append({**claim, "reject_reason": "fabricated_term",
                                 "missing_entities": fabricated})
                continue
            # buraya gelindiyse kalan tüm soft_missing terimleri korpusta
            # (varyantıyla) var → yanlış-atıf sinyali, aşağıda FLAG'lenir
        flags += [{"term": t, "reason": "term_not_in_cited_source"}
                  for t in soft_missing]

        # Katman 2 — ANLAMSAL: iddia, atıf yaptığı chunk'lardan birine yakın mı?
        # İddia embed'i profilin sorgu önekini alır, chunk'lar öneksiz (S2
        # ölçümü, açık karar #2): bge'de simetrik/öneksiz modda alakalı-saçma
        # boşluğu YOKTU (0.536 < 0.575), önekli modda açıldı (0.629 > 0.572).
        # MiniLM profilinde önek boş → eski davranış birebir.
        claim_vec = embed_texts([QUERY_PREFIX + text])[0]
        chunk_vecs = embed_texts([by_id[cid]["text"] for cid in known])
        best = float(max(np.dot(chunk_vecs, claim_vec)))

        if best < threshold:
            rejected.append({**claim, "reject_reason": "low_support",
                             "support_score": round(best, 3)})
            continue

        sources = [{
            "chunk_id": cid,
            "url": by_id[cid]["metadata"].get("source_url", ""),
            "scraped_at": by_id[cid]["metadata"].get("scraped_at", ""),
        } for cid in known]
        verified.append({**claim, "chunk_ids": known,
                         "support_score": round(best, 3), "sources": sources,
                         "flags": flags})

    return verified, rejected


def node_grounding(state: dict) -> dict:
    """Graph node'u: taslak iddiaları doğrular, nihai raporu kurar."""
    context = list(state.get("general_chunks", []))
    for hits in state.get("package_hits", {}).values():
        context.extend(hits)

    # Sürüm numaraları iddialarda meşru olarak geçer ("22.04'ten 24.04'e...")
    # ama her chunk'ta yazmayabilir — sözcüksel kontrolde muaf tut.
    verified, rejected = verify_claims(
        state.get("draft_claims", []), context,
        allowed_terms=(state["current_version"], state["target_version"]),
        corpus_vocab=corpus_vocab_for(state["target_version"]),
    )

    not_found = [
        f"A draft statement was removed because it lacked a verifiable source "
        f"({c.get('reject_reason')}): \"{(c.get('text') or '')[:120]}\""
        for c in rejected
    ]

    # v2.1: reddedilenlerin TAM detayı da rapora girer (şeffaflık + denetim:
    # accuracy audit RED'in haklı olup olmadığını ancak tam metinle yargılayabilir)
    rejected_detail = [{
        "text": c.get("text", ""),
        "reject_reason": c.get("reject_reason"),
        "missing_entities": c.get("missing_entities", []),
        "support_score": c.get("support_score"),
        "chunk_ids": c.get("chunk_ids", []),
    } for c in rejected]

    # "Etkilenen paketlerin" listesi kullanıcının GERÇEK envanteriyle kesişmeli.
    # Gevşek eşleme: "openssh" ↔ "openssh-server", "python" ↔ "python2" gibi
    # ad varyasyonlarını yakalar; envanterde hiç karşılığı olmayanlar elenir.
    installed = [p.lower() for p in (state.get("packages") or [])]

    def _is_installed(name: str) -> bool:
        n = name.lower()
        return any(n in p or p in n for p in installed)

    report = {
        "host": state.get("host"),   # None → lokal analiz (v2: raporda hedef görünür)
        "current_version": state["current_version"],
        "target_version": state["target_version"],
        # S4 (açık karar #4): raporu üreten LLM beyanı — A/B koşuları ve
        # denetim izleri kendiliğinden etiketli olur.
        "model": state.get("used_model", LLM_MODEL),
        "summary": state.get("draft_summary", ""),
        "claims": verified,
        "not_found_notes": not_found,
        "rejected_claims": rejected_detail,
        "package_candidates": state.get("package_candidates", []),
        "affected_packages": sorted({c.get("affected_package")
                                     for c in verified
                                     if c.get("affected_package")
                                     and _is_installed(c["affected_package"])}),
        "freshness": state.get("freshness", {}),
        "warnings": state.get("warnings", []),
        "stats": {
            "draft_claims": len(state.get("draft_claims", [])),
            "verified": len(verified),
            "rejected": len(rejected),
            "flagged": sum(1 for c in verified if c.get("flags")),
        },
    }
    return {"report": report}
