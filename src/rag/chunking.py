"""M3 / Sprint R1 — Token-bazlı chunking.

Processed JSON zarfındaki bölümleri, embedding modelinin token bütçesine
sığan parçalara böler. Tasarım kararları (bkz. master-plan.md, FAZ 1):

- Bölme sınırı CÜMLE ('. ' bazlı) — verimizde '\\n\\n' paragraf ayracı yok.
- Uzunluk kontrolü TOKEN bazlı; sayaç dışarıdan enjekte edilir (count_tokens),
  böylece bu modül embedding modeline bağımlı olmadan test edilebilir.
- Tek cümle bütçeyi aşarsa token bazında sert bölme (fallback) — sessiz
  kırpma asla olmasın.
- Chunk id deterministik: "{version}_{section_id}_{idx}" → Chroma'da upsert
  ile mükerrer kayıt önlenir.
- Sphinx'in '¶' permalink artıkları burada temizlenir.
- Başlık chunk metnine önek olarak eklenir ("Known Issues: ...") — sorgudaki
  başlık kelimeleri ("known issues in 24.04") retrieval isabetini artırır.
"""

import re
from dataclasses import dataclass, field
from typing import Callable

MAX_TOKENS = 250        # MiniLM sınırı 256 (+2 özel token payı); bge-small 512
                        # destekler ama tavan V0 chunking'le SABİT — sınırlar
                        # tokenizer'la birlikte kilitli (CHUNK_TOKENIZER_MODEL)
MIN_WORDS = 5           # bundan kısa chunk'lar gürültü sayılır, elenir


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict = field(default_factory=dict)


def clean_text(text: str) -> str:
    """'¶' artıklarını siler, tüm boşlukları tek boşluğa indirger."""
    return " ".join(text.replace("¶", "").split())


def split_sentences(text: str) -> list[str]:
    """Metni cümle sonlarından böler (. ! ? ardından boşluk).

    Kısaltmalarda (örn. "e.g. ") mükemmel değildir; RAG için yeterli —
    yanlış bölünen bir kısaltma sadece iki kısa cümle üretir, bilgi kaybolmaz.
    """
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _hard_split(text: str, count_tokens: Callable[[str], int],
                max_tokens: int) -> list[str]:
    """Bütçeye sığmayan TEK cümleyi kelime kelime biriktirerek böler.

    Cümle sınırı korunamıyor (cümlenin kendisi çok uzun) ama hiçbir parça
    bütçeyi aşmaz → embedding'de sessiz kırpma yaşanmaz.
    """
    pieces, buf = [], []
    for word in text.split():
        candidate = buf + [word]
        if buf and count_tokens(" ".join(candidate)) > max_tokens:
            pieces.append(" ".join(buf))
            buf = [word]
        else:
            buf = candidate
    if buf:
        pieces.append(" ".join(buf))
    return pieces


def _pack_sentences(sentences: list[str], count_tokens: Callable[[str], int],
                    max_tokens: int) -> list[str]:
    """Cümleleri sırayla biriktirir; bütçe dolunca chunk kapatır."""
    chunks, buf = [], []
    for sent in sentences:
        if count_tokens(sent) > max_tokens:
            # Cümlenin kendisi bütçeden büyük: önce eldekini kapat, sonra sert böl
            if buf:
                chunks.append(" ".join(buf))
                buf = []
            chunks.extend(_hard_split(sent, count_tokens, max_tokens))
            continue

        candidate = buf + [sent]
        if buf and count_tokens(" ".join(candidate)) > max_tokens:
            chunks.append(" ".join(buf))
            buf = [sent]
        else:
            buf = candidate
    if buf:
        chunks.append(" ".join(buf))
    return chunks


def _slugify(title: str) -> str:
    """section_id yoksa başlıktan url-uyumlu bir kimlik üretir (fallback)."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


def chunk_section(section: dict, envelope: dict,
                  count_tokens: Callable[[str], int],
                  max_tokens: int = MAX_TOKENS) -> list[Chunk]:
    """Tek bir bölümü Chunk listesine çevirir.

    - section: processed JSON'daki {section, section_id, content, source_url, version}
    - envelope: zarf {version, source_url, scraped_at, ...} — scraped_at buradan gelir
    """
    title = clean_text(section.get("section") or "")
    content = clean_text(section.get("content") or "")
    if not content or len(content.split()) < MIN_WORDS:
        return []

    section_id = section.get("section_id") or _slugify(title)

    # Başlık öneki bütçeden düşülür ki önek + içerik toplamı sınırı aşmasın
    prefix = f"{title}: " if title else ""
    budget = max_tokens - (count_tokens(prefix) if prefix else 0)

    texts = _pack_sentences(split_sentences(content), count_tokens, budget)

    version = section.get("version") or envelope.get("version", "")
    chunks = []
    idx = 0
    for text in texts:
        if len(text.split()) < MIN_WORDS:
            continue                      # sert bölme kırıntılarını da ele
        cid = f"{version}_{section_id}_{idx}"
        chunks.append(Chunk(
            id=cid,
            text=prefix + text,
            metadata={
                "id": cid,                # Chroma res["ids"]'e ek olarak metadata'da da
                "version": version,
                "section_title": title,
                "section_id": section_id,
                "source_url": section.get("source_url")
                              or envelope.get("source_url", ""),
                "scraped_at": envelope.get("scraped_at", ""),
            },
        ))
        idx += 1
    return chunks


def chunk_release_notes(envelope: dict,
                        count_tokens: Callable[[str], int],
                        max_tokens: int = MAX_TOKENS) -> list[Chunk]:
    """Bir sürümün processed JSON zarfını komple Chunk listesine çevirir."""
    chunks = []
    for section in envelope.get("sections", []):
        chunks.extend(chunk_section(section, envelope, count_tokens, max_tokens))
    return chunks
