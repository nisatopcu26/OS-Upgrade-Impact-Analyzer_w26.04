"""Zincir upgrade Aşama 1 — yol hesabı testleri (saf, I/O'suz*).

*test_default_chain_matches_versions_json tek istisna: gerçek config'i okur
(ağ/model yok) — lts_chain ile versions.json'ın sessizce ayrışmasını yakalar.
"""

import json
from pathlib import Path

from src.upgrade_path.path import compute_path, lts_chain

CHAIN = ["18.04", "20.04", "22.04", "24.04"]   # sahte zincir (enjeksiyon deseni)


def test_full_chain_18_to_24():
    p = compute_path("18.04", "24.04", chain=CHAIN)
    assert p["error"] is None
    assert p["path"] == ["18.04", "20.04", "22.04", "24.04"]
    assert p["legs"] == [("18.04", "20.04"), ("20.04", "22.04"),
                         ("22.04", "24.04")]
    assert p["is_direct"] is False
    assert p["skipped_intermediates"] == ["20.04", "22.04"]


def test_direct_leg_is_direct():
    p = compute_path("22.04", "24.04", chain=CHAIN)
    assert p["is_direct"] is True
    assert p["legs"] == [("22.04", "24.04")]
    assert p["skipped_intermediates"] == []


def test_two_leg_path():
    p = compute_path("20.04", "24.04", chain=CHAIN)
    assert len(p["legs"]) == 2 and p["skipped_intermediates"] == ["22.04"]


def test_unknown_version_meaningful_error():
    # zincir dışı sürüm → uydurma yol YOK, anlamlı hata var
    for cur, tgt in (("19.10", "24.04"), ("18.04", "25.04")):
        p = compute_path(cur, tgt, chain=CHAIN)
        assert p["path"] is None and p["legs"] == []
        assert "zincirinde değil" in p["error"]


def test_downgrade_and_same_version_error():
    assert "yeni olmalı" in compute_path("24.04", "18.04", chain=CHAIN)["error"]
    assert "yeni olmalı" in compute_path("22.04", "22.04", chain=CHAIN)["error"]


def test_injected_chain_used_not_disk():
    # enjekte zincirde 26.04 var — diskte yok; enjeksiyon gerçekten kullanılıyor
    p = compute_path("24.04", "26.04", chain=CHAIN + ["26.04"])
    assert p["error"] is None and p["is_direct"] is True


def test_default_chain_matches_versions_json():
    # lts_chain ↔ versions.json ayrışma nöbetçisi (routes da buna dayanıyor)
    cfg = Path(__file__).resolve().parents[1] / "config" / "versions.json"
    expected = sorted(json.loads(cfg.read_text(encoding="utf-8"))["versions"])
    assert lts_chain() == expected
