"""M1 — Detector testleri (pytest). (+ v2: uzak-mod mock testleri)"""

from src.detector.os_detector import read_os_release, detect_os
from src.remote.ssh_runner import RemoteResult


def _write(tmp_path, content):
    p = tmp_path / "os-release"
    p.write_text(content, encoding="utf-8")
    return p


def test_normal(tmp_path):
    p = _write(tmp_path,
        'ID=ubuntu\nVERSION_ID="22.04"\nVERSION_CODENAME=jammy\n'
        'PRETTY_NAME="Ubuntu 22.04.5 LTS"\n')
    info = read_os_release(p)
    assert info["id"] == "ubuntu"
    assert info["version_id"] == "22.04"        # tırnak temizlendi
    assert info["codename"] == "jammy"


def test_missing_version_id(tmp_path):
    # Bozuk/eksik içerik — çökmemeli, version_id None olmalı
    info = read_os_release(_write(tmp_path, "ID=ubuntu\n"))
    assert info["id"] == "ubuntu"
    assert info["version_id"] is None


def test_missing_file(tmp_path):
    assert read_os_release(tmp_path / "yok") is None


def test_ubuntu_codename_fallback(tmp_path):
    # VERSION_CODENAME yok -> UBUNTU_CODENAME'e düşmeli
    info = read_os_release(_write(tmp_path,
        "ID=ubuntu\nVERSION_ID=22.04\nUBUNTU_CODENAME=jammy\n"))
    assert info["codename"] == "jammy"


def test_detect_os_contract():
    # Her durumda standart anahtarlar dönmeli (M4 agent'ın güveneceği sözleşme)
    result = detect_os()
    for key in ("distro", "version", "codename", "source"):
        assert key in result


def test_detect_os_real_system():
    # Bu makinede (Ubuntu 22.04) gerçek tespit
    result = detect_os()
    assert result["distro"] == "ubuntu"
    assert result["source"] in ("os-release", "lsb_release")


# --- Roadmap v2 / S6: uzak-mod testleri (mock'lu RemoteResult, lab'sız) -----

def test_detect_os_remote_parses_cat_output(monkeypatch):
    fake = RemoteResult(ok=True, stdout='ID=ubuntu\nVERSION_ID="24.04"\n'
                                        'VERSION_CODENAME=noble\n')
    monkeypatch.setattr("src.detector.os_detector.run_remote",
                        lambda *a, **k: fake)
    info = detect_os(host="u@1.2.3.4")
    assert info["version"] == "24.04" and info["codename"] == "noble"
    assert info["source"] == "os-release(remote)"   # kaynak DOĞRU etiketli


def test_detect_os_remote_unreachable_contract(monkeypatch):
    # Erişilemeyen hedef: uydurma yok — source=None + error (mevcut sözleşme)
    fake = RemoteResult(ok=False, error="timeout (15s)")
    monkeypatch.setattr("src.detector.os_detector.run_remote",
                        lambda *a, **k: fake)
    info = detect_os(host="u@1.2.3.4")
    assert info["version"] is None and info["source"] is None
    assert "error" in info and "u@1.2.3.4" in info["error"]
