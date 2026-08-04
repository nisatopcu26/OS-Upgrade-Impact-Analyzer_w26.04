"""Uzaktan analiz (SSH) — komut çalıştırma katmanı (roadmap v2 / Sprint 1).

Tek ve merkezi giriş noktası: tüm SSH işleri run_remote'tan geçer (dağınık
`ssh ...` çağrıları yok). host=None ise aynı arayüzle LOKAL çalışır — detector
ve inventory'nin çift-mod olabilmesinin temeli.

Neden subprocess + sistem ssh (paramiko değil): anahtarlar ssh-copy-id ile
kurulu, sistem ssh bunları otomatik kullanır; sıfır ek bağımlılık. Arayüz sabit
kaldığı için ileride paramiko'ya geçiş izole kalır.

Güvenlik (v2): host değeri API/UI'dan serbest metin gelir. OpenSSH '-' ile
başlayan argümanı hostname değil SEÇENEK olarak yorumlar — "-oProxyCommand=..."
gibi bir "host", kontrol düğümünde keyfî komut çalıştırırdı (argüman
enjeksiyonu). validate_host'tan geçmeyen hiçbir string subprocess'e ulaşmaz.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

# kullanici@hedef kalıbı: Linux kullanıcı adı (küçük harf/_ ile başlar) +
# IP ya da hostname. '-' ile başlayan, boşluk/noktalı virgül içeren her şey
# otomatik RED. Bilinçli olarak dar — IPv6/port gerekirse testli genişletilir.
_HOST_RE = re.compile(r"^[a-z_][a-z0-9._-]*@[a-z0-9][a-z0-9.-]*$")


def validate_host(host: str) -> bool:
    """host string'i güvenli 'kullanici@hedef' kalıbında mı?"""
    return bool(_HOST_RE.match(host or ""))


@dataclass
class RemoteResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


def run_remote(cmd: list[str], host: str | None = None,
               timeout: int = 15) -> RemoteResult:
    """cmd'yi host'ta çalıştırır; host=None ise LOKAL çalışır (tek arayüz).

    Her hata türü → RemoteResult(ok=False, error=...) — exception fırlatmaz,
    akışı çökertmez ("uydurma yok" ilkesinin çalıştırma katmanı karşılığı:
    belirsiz bekleme ya da sessiz çökme yerine net hata).
    """
    if host is not None and not validate_host(host):
        # subprocess'e HİÇ girmeden reddet (argüman enjeksiyonu koruması)
        return RemoteResult(ok=False, error=f"geçersiz host formatı: {host!r}")

    if host:
        full_cmd = [
            "ssh",
            "-o", "BatchMode=yes",          # şifre sorma: anahtar yoksa hemen düş
            "-o", "ConnectTimeout=5",       # bağlantı için ayrı, kısa timeout
            "-o", "StrictHostKeyChecking=accept-new",
            host, *cmd,
        ]
    else:
        full_cmd = cmd

    try:
        proc = subprocess.run(full_cmd, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return RemoteResult(ok=False, error=f"timeout ({timeout}s) — host: {host}")
    except FileNotFoundError:
        return RemoteResult(ok=False, error=f"komut bulunamadı: {full_cmd[0]}")

    if proc.returncode != 0:
        return RemoteResult(ok=False, stdout=proc.stdout, stderr=proc.stderr,
                            error=f"komut başarısız (kod {proc.returncode}): "
                                  f"{proc.stderr.strip()}")
    return RemoteResult(ok=True, stdout=proc.stdout, stderr=proc.stderr)


def is_reachable(host: str) -> bool:
    """Hızlı erişilebilirlik testi — ucuz bir komutla."""
    return run_remote(["true"], host=host, timeout=8).ok
