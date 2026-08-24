"""Apt iliskisel metadata katmani -- izole testler (SSH gerektiren kismi lab)."""
import pytest

from src.detector.apt_relations import get_apt_relations, render_apt_relations_chunk


def test_render_chunk_none_when_empty():
    assert render_apt_relations_chunk("foo", {}, "26.04", "2026-08-21T00:00:00") is None


def test_render_chunk_shape():
    relations = {"Replaces": "samba-libs (<< 2:4.19.0~)",
                "Breaks": "samba-ad-dc (<< 2:4.20.1+dfsg-2~)"}
    chunk = render_apt_relations_chunk("samba", relations, "26.04", "2026-08-21T00:00:00")
    assert chunk["id"] == "apt-relations_26.04_samba"
    assert "Replaces samba-libs" in chunk["text"]
    assert "Breaks samba-ad-dc" in chunk["text"]
    assert chunk["metadata"]["source_url"] == "apt-cache:samba"
    assert chunk["metadata"]["section_title"] == "APT Package Relations"


def test_render_chunk_field_order_stable():
    # Breaks/Conflicts/Replaces/Provides sirasi HER ZAMAN ayni (determinizm)
    relations = {"Provides": "php", "Breaks": "x"}
    chunk = render_apt_relations_chunk("php8.5", relations, "26.04", "now")
    breaks_idx = chunk["text"].index("Breaks")
    provides_idx = chunk["text"].index("Provides")
    assert breaks_idx < provides_idx


@pytest.mark.lab
def test_get_apt_relations_real_samba():
    # Gercek 26.04 VM'inde samba'nin bilinen iliskilerini dogrula
    import json
    from pathlib import Path
    hosts = json.loads(
        (Path(__file__).resolve().parents[1] / "config" / "hosts.json")
        .read_text())["hosts"]
    entry = next(h for h in hosts if "26.04" in h["label"])

    from src.remote.ssh_runner import is_reachable
    if not is_reachable(entry["host"]):
        pytest.skip(f"lab VM kapali: {entry['label']}")

    rel = get_apt_relations("samba", host=entry["host"])
    assert "Replaces" in rel
    assert "samba-vfs-modules" in rel["Replaces"]
