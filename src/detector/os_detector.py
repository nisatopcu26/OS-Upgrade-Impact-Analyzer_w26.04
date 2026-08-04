"""M1 — Sistem tespiti (+ roadmap v2 / Sprint 2: uzak mod).

Sistemin dağıtım/sürüm bilgisini en güvenilir kaynaktan (os-release) okur.
Deterministik, LLM yok.

Çift-mod tasarımı (v2): parse ORTAK, I/O moda özel — lokal okuma `open()` ile
(path parametresi ve 6 mevcut test aynen korunur), uzak okuma SSH üzerinden
`cat` ile; ikisi de AYNI parser'dan geçer. ("Lokalde de cat kullan, tek kod
yolu olsun" fikri bilinçli reddedildi: test edilebilirliği bozuyordu.)
"""

from pathlib import Path

from src.remote.ssh_runner import run_remote


OS_RELEASE_PATH = Path("/etc/os-release")


def _parse_os_release(text: str) -> dict:
    """KEY=VALUE formatını parse eder; değerler bazen tırnaklı.

    Lokal (dosya) ve uzak (ssh cat) okumanın ORTAK parser'ı.
    """
    raw = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue                      # boş satır / yorum / bozuk satırı atla
        key, value = line.split("=", 1)   # sadece İLK '='den böl (değerde '=' olabilir)
        value = value.strip().strip('"').strip("'")   # tırnakları temizle
        raw[key.strip()] = value

    return {
        "id": raw.get("ID"),
        "version_id": raw.get("VERSION_ID"),
        # codename yoksa UBUNTU_CODENAME'e düş
        "codename": raw.get("VERSION_CODENAME") or raw.get("UBUNTU_CODENAME"),
        "pretty_name": raw.get("PRETTY_NAME"),
    }


def read_os_release(path: Path = OS_RELEASE_PATH) -> dict | None:
    """LOKAL /etc/os-release okuma — imza ve davranış DEĞİŞMEZ
    (testler path enjeksiyonuyla sahte dosya verir). Dosya yoksa None."""
    if not path.exists():
        return None
    return _parse_os_release(path.read_text(encoding="utf-8"))


def read_os_release_remote(host: str) -> dict | None:
    """UZAK /etc/os-release okuma — cat çıktısı aynı parser'dan geçer."""
    res = run_remote(["cat", "/etc/os-release"], host=host)
    return _parse_os_release(res.stdout) if res.ok else None


def read_lsb_release(host: str | None = None) -> dict | None:
    """`lsb_release -a` fallback'i — host=None lokal, verilirse uzak.
    Komut yoksa/başarısızsa None (çift-mod: run_remote üzerinden)."""
    res = run_remote(["lsb_release", "-a"], host=host, timeout=10)
    if not res.ok:
        return None

    fields = {}
    for line in res.stdout.splitlines():
        if ":" not in line:
            continue                      # "No LSB modules..." gibi satırları atla
        key, value = line.split(":", 1)   # "Distributor ID:\tUbuntu"
        fields[key.strip()] = value.strip()

    return {
        "id": (fields.get("Distributor ID") or "").lower() or None,
        "version_id": fields.get("Release") or None,
        "codename": fields.get("Codename") or None,
        "pretty_name": fields.get("Description"),
    }


def detect_os(host: str | None = None) -> dict:
    """Ana fonksiyon: os-release'i dene, olmazsa lsb_release'e düş.

    host=None → lokal (eski davranış birebir); host="kullanici@ip" → SSH ile
    uzaktan. Standart format döner: {distro, version, codename, source}.
    source, GERÇEK kaynağa göre etiketlenir (ör. "lsb_release(remote)").
    Hiçbiri işe yaramazsa uydurmak yerine source=None + error döner.
    """
    if host:
        readers = [(lambda: read_os_release_remote(host), "os-release(remote)"),
                   (lambda: read_lsb_release(host), "lsb_release(remote)")]
    else:
        readers = [(read_os_release, "os-release"),
                   (read_lsb_release, "lsb_release")]

    try:
        for reader, source in readers:
            info = reader()
            if info and info.get("id") and info.get("version_id"):
                return {
                    "distro": info["id"],
                    "version": info["version_id"],
                    "codename": info.get("codename"),
                    "source": source,
                }
    except Exception as e:
        return {"distro": None, "version": None, "codename": None,
                "source": None, "error": str(e)}

    suffix = f" (host: {host})" if host else ""
    return {
        "distro": None,
        "version": None,
        "codename": None,
        "source": None,
        "error": "Sistem tespit edilemedi (os-release ve lsb_release "
                 f"başarısız){suffix}",
    }
