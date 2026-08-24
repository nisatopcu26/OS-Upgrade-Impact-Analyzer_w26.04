"""NEWS.Debian katmani -- izole testler (SSH/indirme gerektiren kismi lab)."""
import pytest

from src.detector.news_debian import get_news_debian, render_news_debian_chunk


def test_render_chunk_none_when_empty():
    assert render_news_debian_chunk("foo", None, "26.04", "2026-08-21T00:00:00") is None
    assert render_news_debian_chunk("foo", "", "26.04", "2026-08-21T00:00:00") is None


def test_render_chunk_extracts_latest_entry_only():
    # Iki girdili sahte NEWS.Debian -- yalniz EN USTTEKI (en guncel) alinmali
    raw = (
        "pkg (2.0-1) unstable; urgency=medium\n\n"
        "  This is the newest entry, only this should be extracted.\n\n"
        " -- Maintainer <m@example.com>  Mon, 01 Jan 2026 00:00:00 +0000\n\n"
        "pkg (1.0-1) unstable; urgency=low\n\n"
        "  This is an OLD entry, should NOT appear in the chunk.\n\n"
        " -- Maintainer <m@example.com>  Mon, 01 Jan 2020 00:00:00 +0000\n"
    )
    chunk = render_news_debian_chunk("pkg", raw, "26.04", "now")
    assert "newest entry" in chunk["text"]
    assert "OLD entry" not in chunk["text"]


def test_render_chunk_shape():
    chunk = render_news_debian_chunk(
        "samba",
        "samba (2:4.20.1+dfsg-2) unstable; urgency=medium\n\n"
        "  AD-DC functionality split into samba-ad-dc.\n\n"
        " -- M <m@example.com>  Sun, 26 May 2024 00:00:00 +0000\n",
        "26.04", "2026-08-21T00:00:00",
    )
    assert chunk["id"] == "news-debian_26.04_samba"
    assert "AD-DC functionality split" in chunk["text"]
    assert chunk["metadata"]["source_url"] == "news-debian:samba"
    assert chunk["metadata"]["section_title"] == "Debian NEWS.Debian"


@pytest.mark.lab
def test_get_news_debian_real_samba():
    import json
    from pathlib import Path
    hosts = json.loads(
        (Path(__file__).resolve().parents[1] / "config" / "hosts.json")
        .read_text())["hosts"]
    entry = next(h for h in hosts if "26.04" in h["label"])

    from src.remote.ssh_runner import is_reachable
    if not is_reachable(entry["host"]):
        pytest.skip(f"lab VM kapali: {entry['label']}")

    news = get_news_debian("samba", host=entry["host"])
    assert news is not None
    assert "samba-ad-dc" in news.lower()
