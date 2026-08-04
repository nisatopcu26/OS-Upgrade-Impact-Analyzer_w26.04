"""Uzaktan analiz / Sprint 1 — ssh_runner birim testleri (lab'sız, mock'lu).

En kritik kanıt: enjeksiyon denemeleri subprocess'e HİÇ ulaşmıyor —
"-oProxyCommand=..." gibi bir "host", ssh'e seçenek olarak geçseydi kontrol
düğümünde keyfî komut çalıştırırdı.
"""

import subprocess

from src.remote import ssh_runner
from src.remote.ssh_runner import RemoteResult, run_remote, validate_host


def test_validate_host_accepts_lab_pattern():
    assert validate_host("_2204@192.168.122.16")        # gerçek lab kullanıcısı
    assert validate_host("ubuntu1804@192.168.122.103")
    assert validate_host("deploy@web-01.internal")       # hostname de meşru


def test_validate_host_rejects_injection_and_garbage():
    assert not validate_host("-oProxyCommand=touch /tmp/pwned@1.2.3.4")
    assert not validate_host("user@host; rm -rf /")      # kabuk metakarakteri
    assert not validate_host("user@host x")              # boşluk
    assert not validate_host("host-without-user")        # @ yok
    assert not validate_host("")
    assert not validate_host(None)                       # type: ignore[arg-type]


def test_injection_never_reaches_subprocess(monkeypatch):
    called = []
    monkeypatch.setattr(ssh_runner.subprocess, "run",
                        lambda *a, **k: called.append(a))
    r = run_remote(["true"], host="-oProxyCommand=touch /tmp/pwned")
    assert not r.ok and "geçersiz host" in r.error
    assert called == []          # subprocess HİÇ çağrılmadı — asıl kanıt


def test_ssh_command_construction(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(ssh_runner.subprocess, "run", fake_run)
    r = run_remote(["cat", "/etc/os-release"], host="u@1.2.3.4")
    assert r.ok and r.stdout == "ok"
    cmd = captured["cmd"]
    assert cmd[0] == "ssh" and cmd[-3:] == ["u@1.2.3.4", "cat", "/etc/os-release"]
    assert "BatchMode=yes" in cmd            # asılı kalma koruması
    assert "ConnectTimeout=5" in cmd


def test_local_mode_passthrough(monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(ssh_runner.subprocess, "run", fake_run)
    run_remote(["echo", "x"])                # host=None → lokal
    assert captured["cmd"] == ["echo", "x"]  # ssh sarmalaması YOK


def test_timeout_and_nonzero_exit_return_error(monkeypatch):
    def fake_timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 15)

    monkeypatch.setattr(ssh_runner.subprocess, "run", fake_timeout)
    r = run_remote(["true"], host="u@1.2.3.4")
    assert not r.ok and "timeout" in r.error

    def fake_fail(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 255, stdout="",
                                           stderr="Connection refused")

    monkeypatch.setattr(ssh_runner.subprocess, "run", fake_fail)
    r = run_remote(["true"], host="u@1.2.3.4")
    assert not r.ok and "255" in r.error and "Connection refused" in r.error


def test_missing_command_local(monkeypatch):
    def fake_notfound(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(ssh_runner.subprocess, "run", fake_notfound)
    r = run_remote(["apt-mark", "showmanual"])           # lokal mod
    assert not r.ok and "apt-mark" in r.error            # doğru komut adıyla
