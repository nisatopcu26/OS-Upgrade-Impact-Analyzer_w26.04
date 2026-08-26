"""Faz 2 — Paket envanteri (+ roadmap v2 / Sprint 3: uzak mod).

Kullanıcının BİLİNÇLİ kurduğu paketleri toplar. `dpkg -l` binlerce otomatik
bağımlılık döndürür; `apt-mark showmanual` ise elle kurulanları — upgrade
raporunda kullanıcının umursadığı liste budur. (Lab notu: eski kurulumlarda
taban sistem de "manual" işaretli olabilir — 18.04 VM'inde ~430 paket ölçüldü;
timeout ve testler bu gerçeğe göre.)

detect_os() ile aynı ilkeler: deterministik, LLM'siz, hiçbir durumda çökmez,
komut yoksa/erişilemezse uydurmak yerine boş envanter + error döner.
"""

from datetime import datetime

from src.detector.os_detector import detect_os
from src.remote.ssh_runner import run_remote

# 2026-08-26 (RHEL-ailesi genislemesi): apt-mark'in dnf karsiligi. Rocky
# Linux 10.2'de gercek VM'e karsi dogrulandi -- sudo GEREKTIRMEZ (salt
# okunur sorgu), apt-mark ile ayni yetki seviyesinde. --qf '%{name}' ile
# insan-okur NEVRA formati (ad-surum-release.mimari) hic parse edilmez --
# paket adlari kendi icinde tire tasiyabildigi icin (grub2-efi-aa64 gibi)
# string bolme guvenilir olmazdi.
_RHEL_FAMILY = {"rhel", "rocky", "almalinux", "centos", "fedora"}


def _is_rhel_family(host: str | None) -> bool:
    """Hedefin (host=None ise lokalin) RHEL ailesinden olup olmadigini
    detect_os() ile sorar -- distro adini burada tekrar sabitlemek yerine
    tek gercek kaynaga (os_detector) basvurulur."""
    info = detect_os(host=host)
    return (info.get("distro") or "").lower() in _RHEL_FAMILY


def list_manual_packages(host: str | None = None) -> list[str] | None:
    """Kullanicinin bilincli kurdugu paketleri doner; basarisizsa None.

    Debian-ailesi: `apt-mark showmanual`. RHEL-ailesi: `dnf repoquery
    --userinstalled --qf '%{name}'` (2026-08-26 eklendi, Rocky Linux 10.2'de
    dogrulandi). Hangi komutun kullanilacagina distro tespitiyle karar
    verilir -- sessiz varsayim yok, tespit basarisizsa None doner.
    host=None -> lokal, verilirse SSH ile uzak (cift-mod: run_remote uzerinden).
    sorted() korunur -- node_package_intersect'in aday kesmesi deterministik kalsin.
    """
    if _is_rhel_family(host):
        res = run_remote(["dnf", "repoquery", "--userinstalled", "--qf", "%{name}"],
                         host=host, timeout=30)
    else:
        res = run_remote(["apt-mark", "showmanual"], host=host, timeout=30)

    if not res.ok:
        return None
    return sorted(line.strip() for line in res.stdout.splitlines() if line.strip())


def get_package_version(name: str, host: str | None = None) -> str | None:
    """Kurulu paketin surumunu doner; paket yoksa None.

    Debian-ailesi: `dpkg-query`. RHEL-ailesi: `rpm -q --qf '%{VERSION}'`
    (2026-08-26 eklendi, Rocky Linux 10.2'de dogrulandi -- rpm de dpkg-query
    gibi sonuna yeni satir eklemiyor).
    """
    if _is_rhel_family(host):
        res = run_remote(["rpm", "-q", "--qf", "%{VERSION}", name], host=host, timeout=10)
    else:
        res = run_remote(["dpkg-query", "-W", "-f=${Version}", name], host=host, timeout=10)
    return (res.stdout.strip() or None) if res.ok else None


def get_inventory(with_versions: bool = False, host: str | None = None) -> dict:
    """Standart envanter sözleşmesi (agent'ın tool olarak çağıracağı format).

    {"packages": [...] | {name: version}, "count": N,
     "source": "apt-mark" | "apt-mark(remote)", "collected_at": iso, ["error": ...]}

    with_versions=True her paket için dpkg-query çalıştırır (yavaş) — rapor
    için paket ADI yeterli olduğundan varsayılan kapalı. KARAR (v2): uzakta
    with_versions YOK SAYILIR — paket başına ayrı SSH turu demek olurdu
    (18.04'te ~430 tur). Toplu sorgu = v2.2 genişletmesi.
    """
    names = list_manual_packages(host=host)
    if names is None:
        where = f"host: {host}" if host else "lokal sistem"
        return {
            "packages": [], "count": 0, "source": None,
            "collected_at": datetime.now().isoformat(),
            "error": f"Paket envanteri alınamadı ({where} — apt-mark "
                     "yok/başarısız ya da erişilemedi)",
        }

    packages = ({n: get_package_version(n) for n in names}
                if (with_versions and not host) else names)
    is_rhel = _is_rhel_family(host)
    base_source = "dnf" if is_rhel else "apt-mark"
    return {
        "packages": packages, "count": len(names),
        "source": f"{base_source}(remote)" if host else base_source,
        "collected_at": datetime.now().isoformat(),
    }
