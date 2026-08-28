"""2026-08-27 (RHEL-ailesi genislemesi) — Rocky scraper'i icin kalici testler.

Saf mantik (parse, slug, URL uretimi) agsiz test edilir. Gercek GitHub
cekimi ayri, lab-isaretli bir testte -- diger kanit katmanlarindaki
(apt_relations, news_debian) desenle tutarli.
"""

import pytest

from src.scraper.rocky_scraper import (
    build_source_url,
    parse_release_notes_md,
    rocky_version_to_filename,
    scrape_rocky_release_notes,
    _strip_front_matter,
)


def test_rocky_version_to_filename():
    assert rocky_version_to_filename("10.2") == "10_2"
    assert rocky_version_to_filename("10.0") == "10_0"


def test_build_source_url():
    url = build_source_url("10.2")
    assert url == (
        "https://raw.githubusercontent.com/rocky-linux/documentation/"
        "main/docs/releases/release_notes/10_2.md"
    )


def test_strip_front_matter_removes_yaml():
    md = "---\ntitle: Test\ntags: [x]\n---\n\n## Real Content\nHello."
    result = _strip_front_matter(md)
    assert "title:" not in result
    assert "## Real Content" in result


def test_strip_front_matter_noop_when_absent():
    md = "## No Front Matter\nJust content."
    assert _strip_front_matter(md) == md


def test_parse_release_notes_md_basic_sections():
    md = (
        "## First Section\n"
        "Some content here about chrony 4.8.\n\n"
        "### Subsection\n"
        "More detail about postgresql 18.\n"
    )
    sections = parse_release_notes_md(md, version="rocky-10.2", source_url="https://x/10_2.md")
    assert len(sections) == 2
    assert sections[0]["section"] == "First Section"
    assert "chrony" in sections[0]["content"]
    assert sections[1]["section"] == "Subsection"
    assert "postgresql" in sections[1]["content"]
    for s in sections:
        assert s["version"] == "rocky-10.2"
        assert s["source_url"] == "https://x/10_2.md"


def test_parse_release_notes_md_ignores_level1_header():
    # Tek '#' basligi (h1) yakalanmamali -- yalniz ## ### #### section sayilir
    md = "# Rocky Linux 10.2\nIntro text.\n\n## Real Section\nReal content.\n"
    sections = parse_release_notes_md(md, version="rocky-10.2", source_url="https://x")
    assert len(sections) == 1
    assert sections[0]["section"] == "Real Section"


def test_parse_release_notes_md_section_id_is_deterministic_slug():
    md = "## Infrastructure Services\nSome content about databases.\n"
    sections = parse_release_notes_md(md, version="rocky-10.2", source_url="https://x")
    assert sections[0]["section_id"] == "infrastructure-services"
    assert sections[0]["section_id"] is not None  # None birakilsaydi extra_urls
                                                    # disambiguation devreye girmezdi


def test_parse_release_notes_md_empty_section_skipped():
    md = "## Empty Section\n\n## Real Section\nActual content here.\n"
    sections = parse_release_notes_md(md, version="rocky-10.2", source_url="https://x")
    # Bos bolum (icerik yok) elenmeli
    titles = [s["section"] for s in sections]
    assert "Empty Section" not in titles
    assert "Real Section" in titles


@pytest.mark.lab
def test_scrape_rocky_release_notes_real_network():
    """Gercek GitHub'dan 10.2'yi ceker -- ag erisimi gerektirir (VM degil,
    genel internet). Diger kanit katmanlarindaki lab-testi deseniyle
    tutarli isaretlenir."""
    sections = scrape_rocky_release_notes("10.2")
    if not sections:
        pytest.skip("GitHub'a erisilemedi ya da format degisti")

    assert len(sections) > 0
    titles = [s["section"] for s in sections]
    assert "Rocky Linux 10.2" in titles
    # section_id'ler benzersiz olmali (ayni dosya icinde)
    ids = [s["section_id"] for s in sections]
    assert len(ids) == len(set(ids))


def test_version_key_compares_correctly_across_formats():
    """2026-08-28: duz string karsilastirmasi ('rocky-10.2' <= 'rocky-9.8')
    YANLIS sonuc veriyordu (karakter-bazli, '1' < '9'). _version_key,
    sayisal parcalari cikarip tuple karsilastirmasi yapar -- format
    bagimsiz dogru siralama."""
    from src.agent.nodes import _version_key

    # Ubuntu formatinin hala dogru calistigini dogrula (regresyon)
    assert _version_key("24.04") < _version_key("26.04")

    # Rocky formatinda ONCEDEN YANLIS olan durum simdi dogru
    assert _version_key("rocky-9.8") < _version_key("rocky-10.2")
    assert not (_version_key("rocky-10.2") <= _version_key("rocky-9.8"))


def test_parse_release_notes_md_dedups_repeated_headings_on_same_page():
    """2026-08-28: Rocky 9 serisinin bazi sayfalarinda (orn. 9_1.md) AYNI
    SAYFA icinde ayni baslik (orn. 'Other Changes') birden fazla alt bolumde
    tekrarlaniyor -- gercek 9->10 senaryosu test edilirken bulundu
    (ChromaDB DuplicateIDError). Sayfa-ici sayac (-1, -2, ...) ekliyor."""
    from src.scraper.rocky_scraper import parse_release_notes_md

    md = (
        "## Section A\n"
        "First content block here.\n\n"
        "## Other Changes\n"
        "First occurrence of a repeated title.\n\n"
        "## Section B\n"
        "Some other content.\n\n"
        "## Other Changes\n"
        "Second occurrence of the same title.\n\n"
        "## Other Changes\n"
        "Third occurrence.\n"
    )
    sections = parse_release_notes_md(md, version="test-ver", source_url="https://x")
    ids = [s["section_id"] for s in sections]

    assert len(ids) == len(set(ids)), "section_id'ler benzersiz olmali"
    assert "other-changes" in ids
    assert "other-changes-1" in ids
    assert "other-changes-2" in ids
