"""RHEL-ailesi (Rocky Linux) release notes scraper.

Rocky'nin release notes'u GitHub'daki documentation reposunda saf markdown
olarak barinir. HTML parse etmek yerine dogrudan raw markdown cekilir --
daha az kirilgan, tek format (Ubuntu'nun wiki+sphinx ikili formatinin aksine).

Kaynak: https://raw.githubusercontent.com/rocky-linux/documentation/main/docs/releases/release_notes/{version}.md
Dosya adi kalibi (gercek repo'da dogrulandi): "10_2.md", "10_1.md", "10_0.md".

parse_release_notes_md() ayni JSON semasini (version, section, section_id,
content, source_url) doner -- ubuntu_scraper.py ile ayni sozlesme. section_id
kasitli olarak None birakilir: chunking.py'nin mevcut slug-fallback mekanizmasi
zaten bunu tutarli sekilde uretiyor -- slug mantigini burada tekrarlamiyoruz.
"""
import re

from src.scraper.base_scraper import fetch_page, save_raw_html


def _slugify(title: str) -> str:
    """Basligi chunk-kimligi-uyumlu bir slug'a cevirir (kucuk harf, tire
    ayracli). section_id'yi None birakmak yerine bunu kullaniyoruz: aksi
    halde scrape_version()'daki extra_urls disambiguation mantigi
    (s.get("section_id") kontrolu) hic devreye girmez, 10.0/10.1/10.2'de
    ayni basligin (orn. "Kernel") chunk kimlikleri CAKISIR."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


RAW_BASE_URL = "https://raw.githubusercontent.com/rocky-linux/documentation/main/docs/releases/release_notes"


def rocky_version_to_filename(version: str) -> str:
    """'10.2' -> '10_2' (Rocky'nin dosya adlandirma kalibi, '.' yerine '_')."""
    return version.replace(".", "_")


def build_source_url(version: str) -> str:
    filename = rocky_version_to_filename(version)
    return f"{RAW_BASE_URL}/{filename}.md"


def _strip_front_matter(md: str) -> str:
    """Basindaki YAML front matter'i (--- ... ---) atlar."""
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            return md[end + 4:]
    return md


def parse_release_notes_md(md: str, version: str, source_url: str) -> list[dict]:
    """Rocky'nin markdown release notes'unu ubuntu_scraper ile AYNI semaya parse eder.

    Satir satir gezip ## / ### / #### basliklarini bolum sinirlari olarak
    kullanir; her bolumun altindaki tum satirlari icerik olarak toplar.
    """
    md = _strip_front_matter(md)
    lines = md.splitlines()

    heading_re = re.compile(r"^(#{2,4})\s+(.+?)\s*$")

    sections = []
    current_title = None
    buf: list[str] = []
    # 2026-08-28 DUZELTME: Rocky 9 serisinin bazi sayfalarinda (orn. 9_1.md)
    # AYNI SAYFA icinde ayni baslik (orn. "Other Changes") birden fazla alt
    # bolumde tekrarlaniyor -- extra_urls disambiguation'i (sayfa-lar-arasi)
    # bunu cozmuyordu, ayni sayfa icinde section_id CAKISMASINA yol aciyordu
    # (ChromaDB DuplicateIDError). Sayfa-ici sayac ekleniyor.
    slug_counts: dict[str, int] = {}

    def _flush():
        if current_title is None:
            return
        content = "\n".join(buf).strip()
        content = re.sub(r"\n{3,}", "\n\n", content)
        if content:
            base_slug = _slugify(current_title)
            count = slug_counts.get(base_slug, 0)
            slug_counts[base_slug] = count + 1
            section_id = base_slug if count == 0 else f"{base_slug}-{count}"
            sections.append({
                "version": version,
                "section": current_title,
                "section_id": section_id,
                "content": content,
                "source_url": source_url,
            })

    for line in lines:
        m = heading_re.match(line)
        if m:
            _flush()
            current_title = m.group(2).strip()
            buf = []
        else:
            if current_title is not None:
                buf.append(line)
    _flush()

    return sections


def scrape_rocky_release_notes(version: str) -> list[dict]:
    """Ana giris noktasi: versiyon icin gercek markdown'i ceker, parse eder.

    Basarisiz olursa (ag hatasi, 404) BOS liste doner -- uydurma icerik
    olusturulmaz.
    """
    source_url = build_source_url(version)
    md = fetch_page(source_url)
    if md is None:
        return []

    save_raw_html(md, version, suffix="_rocky")
    return parse_release_notes_md(md, version, source_url)
