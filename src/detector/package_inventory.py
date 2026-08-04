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

from src.remote.ssh_runner import run_remote


def list_manual_packages(host: str | None = None) -> list[str] | None:
    """`apt-mark showmanual` çıktısını liste olarak döner; başarısızsa None.

    host=None → lokal, verilirse SSH ile uzak (çift-mod: run_remote üzerinden).
    sorted() korunur — node_package_intersect'in aday kesmesi deterministik kalsın.
    Timeout 30s: ~430 satırlık legacy envanter + ağ payı (ölçülü gerekçe).
    """
    res = run_remote(["apt-mark", "showmanual"], host=host, timeout=30)
    if not res.ok:
        return None
    return sorted(line.strip() for line in res.stdout.splitlines() if line.strip())


def get_package_version(name: str) -> str | None:
    """Kurulu paketin sürümünü döner (dpkg-query, LOKAL); paket yoksa None."""
    res = run_remote(["dpkg-query", "-W", "-f=${Version}", name], timeout=10)
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
    return {
        "packages": packages, "count": len(names),
        "source": "apt-mark(remote)" if host else "apt-mark",
        "collected_at": datetime.now().isoformat(),
    }
