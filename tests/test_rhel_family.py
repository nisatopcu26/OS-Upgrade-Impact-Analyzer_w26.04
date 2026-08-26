"""2026-08-26 (RHEL-ailesi genislemesi) — gercek Rocky Linux 10.2 VM'ine karsi
entegrasyon testleri. test_remote_lab.py ile ayni desen: host'lar
config/hosts.json'dan okunur, VM kapaliysa FAIL degil SKIP.

Bu testler, detect_os() ve package_inventory'nin RHEL-ailesini (dnf/rpm)
gercekten dogru tespit edip kullandigini -- ve Ubuntu-ailesi davranisini
BOZMADIGINI -- kanitlar.

Kullanim:
  pytest -m lab            # sadece lab kaniti
  pytest tests/test_rhel_family.py -v
"""

import json
from functools import lru_cache
from pathlib import Path

import pytest

from src.detector.os_detector import detect_os
from src.detector.package_inventory import get_inventory, get_package_version
from src.remote.ssh_runner import is_reachable

pytestmark = pytest.mark.lab

_HOSTS = json.loads(
    (Path(__file__).resolve().parents[1] / "config" / "hosts.json")
    .read_text(encoding="utf-8"))["hosts"]


@lru_cache(maxsize=None)
def _reachable(host: str) -> bool:
    return is_reachable(host)


def _rocky_entry() -> dict:
    return next(h for h in _HOSTS if "Rocky" in h["label"])


def _skip_if_down(entry: dict) -> None:
    if not _reachable(entry["host"]):
        pytest.skip(f"lab VM kapali/erisilemez: {entry['label']}")


def test_detect_os_identifies_rocky_correctly():
    """detect_os(), hic RHEL-ozel kod olmadan Rocky'yi dogru tespit eder --
    bu, mimarinin bastan dagitimdan bagimsiz tasarlandiginin kaniti."""
    entry = _rocky_entry()
    _skip_if_down(entry)

    info = detect_os(host=entry["host"])
    assert info["distro"] == "rocky"
    assert info["version"] == "10.2"
    assert info["source"] == "os-release(remote)"


def test_inventory_uses_dnf_source_label_on_rocky():
    """get_inventory(), Rocky'de dogru kaynagi (dnf) beyan eder -- apt-mark
    degil. Bu, source alaninin RHEL-ailesinde de dogru etiketlendigini
    dogrular (daha once bir hata olarak bulunmus, duzeltilmisti)."""
    entry = _rocky_entry()
    _skip_if_down(entry)

    inv = get_inventory(host=entry["host"])
    assert inv["source"] == "dnf(remote)"
    assert inv["count"] > 0
    assert inv["count"] == len(inv["packages"])


def test_inventory_rocky_minimal_install_has_expected_core_packages():
    """Rocky'nin minimal kurulumu, her zaman bulunmasi beklenen cekirdek
    paketleri (kernel, grub) icerir -- apt-relations/news-debian'daki
    ayni 'mekanizmayi dogrula, spesifik yazilim varsayma' desenine uygun."""
    entry = _rocky_entry()
    _skip_if_down(entry)

    inv = get_inventory(host=entry["host"])
    assert "kernel" in inv["packages"]
    assert "chrony" in inv["packages"]


def test_get_package_version_uses_rpm_on_rocky():
    """get_package_version(), Rocky'de rpm -q kullanir ve gercek bir
    surum dizesi doner (rpm'in NEVRA formati degil, yalniz VERSION)."""
    entry = _rocky_entry()
    _skip_if_down(entry)

    version = get_package_version("chrony", host=entry["host"])
    assert version is not None
    assert version[0].isdigit()  # "4.8" gibi, "chrony-4.8..." degil


def test_ubuntu_family_unaffected_by_rhel_extension():
    """Regresyon kontrolu: RHEL destegi eklendikten SONRA bile, Ubuntu
    VM'lerinde source hala 'apt-mark(remote)' -- iki aile de dogru ayirt
    ediliyor, biri digerini ezmiyor."""
    ubuntu_entry = next(h for h in _HOSTS if "26.04" in h["label"])
    _skip_if_down(ubuntu_entry)

    inv = get_inventory(host=ubuntu_entry["host"])
    assert inv["source"] == "apt-mark(remote)"
