"""Roadmap v2 / Sprint 6 — gerçek lab entegrasyon testleri.

İki katmanlı test stratejisinin 2. katmanı: bu testler GERÇEK VM'lere SSH ile
bağlanır. VM'ler kapalıysa FAIL değil SKIP — suite yeşil kalır (birinci katman,
mock'lu birim testler, her zaman koşar).

Host'lar koda gömülü değil: config/hosts.json tek kaynak (Sprint 0).
Beklenen sürüm, etiketten okunur ("Lab: Ubuntu 22.04 ..." → 22.04).

Kullanım:
  pytest -m lab            # sadece lab kanıtı
  pytest -m "not lab"      # lab'sız hızlı tur
  pytest                   # hepsi (lab kapalıysa lab testleri skipped)
"""

import json
import re
from functools import lru_cache
from pathlib import Path

import pytest

from src.agent.graph import analyze
from src.detector.os_detector import detect_os
from src.detector.package_inventory import get_inventory
from src.remote.ssh_runner import is_reachable

pytestmark = pytest.mark.lab

_HOSTS = json.loads(
    (Path(__file__).resolve().parents[1] / "config" / "hosts.json")
    .read_text(encoding="utf-8"))["hosts"]


@lru_cache(maxsize=None)
def _reachable(host: str) -> bool:
    """Erişilebilirlik testi test başına değil, host başına BİR kez ölçülür."""
    return is_reachable(host)


def _skip_if_down(entry: dict) -> None:
    if not _reachable(entry["host"]):
        pytest.skip(f"lab VM kapalı/erişilemez: {entry['label']}")


def _host_by_version(version: str) -> dict:
    return next(h for h in _HOSTS if version in h["label"])


@pytest.mark.parametrize("entry", _HOSTS, ids=lambda e: e["label"])
def test_detect_version_matches_label(entry):
    _skip_if_down(entry)
    expected = re.search(r"\d\d\.\d\d", entry["label"]).group()
    info = detect_os(host=entry["host"])
    assert info["version"] == expected
    assert info["source"] == "os-release(remote)"


def test_inventory_web_vm_profile():
    entry = _host_by_version("22.04")
    _skip_if_down(entry)
    inv = get_inventory(host=entry["host"])
    assert inv["source"] == "apt-mark(remote)"
    for pkg in ("apache2", "nginx", "php", "postgresql"):   # 2026-07-08'de teyitli
        assert pkg in inv["packages"]


def test_inventory_legacy_vm_is_noisy():
    # 18.04'te taban sistem 'manual' işaretli → ~430 paket (ölçülen gerçek).
    # Gürültülü envanter, iki aşamalı kesiştirmenin gerçekçi stres girdisi.
    entry = _host_by_version("18.04")
    _skip_if_down(entry)
    inv = get_inventory(host=entry["host"])
    assert inv["count"] > 400


def test_two_vms_have_different_inventories():
    # Makineye-özel analiz kanıtı: iki hedef, iki farklı envanter
    a, b = _host_by_version("22.04"), _host_by_version("20.04")
    _skip_if_down(a), _skip_if_down(b)
    inv_a = set(get_inventory(host=a["host"])["packages"])
    inv_b = set(get_inventory(host=b["host"])["packages"])
    assert inv_a != inv_b


def test_unreachable_host_fails_fast_without_llm():
    # .250 lab'da yok — analyze, graph'a/LLM'e girmeden ConnectionError
    # ("uydurma yok"un bağlantı katmanı: rapor üretilmez, dürüst hata)
    with pytest.raises(ConnectionError):
        analyze("24.04", current_version="22.04", packages=[],
                host="ubuntu@192.168.122.250")
