"""Faz 2 — Paket envanteri testleri."""

import subprocess
from unittest import mock

from src.detector.package_inventory import (
    get_inventory, get_package_version, list_manual_packages,
)


def test_real_system_inventory():
    # Bu makine Ubuntu — gerçek envanter mantıklı olmalı
    inv = get_inventory()
    assert inv["source"] == "apt-mark"
    assert inv["count"] > 0
    assert isinstance(inv["packages"], list)
    assert inv["count"] == len(inv["packages"])


def test_known_package_version():
    # python3 her Ubuntu'da kuruludur
    assert get_package_version("python3")


def test_unknown_package_version_none():
    assert get_package_version("boyle-bir-paket-yok-xyz") is None


def test_missing_command_returns_error_not_crash():
    # apt-mark bulunamazsa: çökme yok, boş envanter + error (uydurma yok)
    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        inv = get_inventory()
    assert inv["count"] == 0
    assert inv["packages"] == []
    assert "error" in inv


def test_command_failure_returns_none():
    fail = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="err")
    with mock.patch("subprocess.run", return_value=fail):
        assert list_manual_packages() is None


def test_inventory_contract_keys():
    # Agent'ın (M4) güveneceği sözleşme
    inv = get_inventory()
    for key in ("packages", "count", "source", "collected_at"):
        assert key in inv


# --- Roadmap v2 / S6: uzak-mod testleri (mock'lu RemoteResult, lab'sız) -----

def test_inventory_remote_source_label(monkeypatch):
    from src.remote.ssh_runner import RemoteResult
    fake = RemoteResult(ok=True, stdout="nginx\napache2\n")
    monkeypatch.setattr("src.detector.package_inventory.run_remote",
                        lambda *a, **k: fake)
    inv = get_inventory(host="u@1.2.3.4")
    assert inv["source"] == "apt-mark(remote)"
    assert inv["packages"] == ["apache2", "nginx"]   # sorted korunuyor


def test_inventory_remote_unreachable_contract(monkeypatch):
    from src.remote.ssh_runner import RemoteResult
    fake = RemoteResult(ok=False, error="komut başarısız (kod 255)")
    monkeypatch.setattr("src.detector.package_inventory.run_remote",
                        lambda *a, **k: fake)
    inv = get_inventory(host="u@1.2.3.4")
    assert inv["count"] == 0 and inv["source"] is None and "error" in inv
