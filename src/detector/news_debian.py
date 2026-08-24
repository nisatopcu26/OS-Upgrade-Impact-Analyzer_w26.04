"""M9 (26.04 turu, 3. kanit katmani) -- Debian NEWS.Debian: paket bakimcilarinin
yukselme sirasinda kullaniciyi uyarmak icin yazdigi dogal-dil notlari. Apt
Breaks/Conflicts gibi kisa/yapisal degil, tam cumleler -- LLM'in daha kolay
"iddia"ya cevirebilecegi format (release notes'a daha yakin).

Deterministik -- LLM yok. .deb indirip (kurmadan) icini acar, NEWS.Debian
varsa okur, gecici dosyalari temizler.
"""

import gzip
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def get_news_debian(package: str, host: str | None = None,
                    timeout: int = 30) -> str | None:
    """Bir paketin NEWS.Debian icerigini doner (yoksa None).

    Kurulum yapmaz: apt-get download ile .deb indirir, dpkg-deb -x ile
    disket cikartir, gecici dizini temizler. Basarisizlikta (paket yok,
    NEWS.Debian yok, ag hatasi) sessizce None -- uydurma icerik olusturulmaz.
    """
    workdir_cmd = f"mkdir -p /tmp/_news_probe_{package} && cd /tmp/_news_probe_{package}"
    download_cmd = f"{workdir_cmd} && apt-get download {package} >/dev/null 2>&1"
    extract_cmd = (
        f"{workdir_cmd} && "
        f"f=$(ls *.deb 2>/dev/null | head -1) && "
        f"[ -n \"$f\" ] && dpkg-deb -x \"$f\" extracted/ 2>/dev/null && "
        f"find extracted -iname 'NEWS.Debian*' 2>/dev/null | head -1"
    )
    cleanup_cmd = f"rm -rf /tmp/_news_probe_{package}"

    def _run(cmd: str) -> subprocess.CompletedProcess:
        if host:
            return subprocess.run(["ssh", "-o", "ConnectTimeout=5", host, cmd],
                                  capture_output=True, text=True, timeout=timeout)
        return subprocess.run(cmd, shell=True, capture_output=True,
                              text=True, timeout=timeout)

    try:
        _run(download_cmd)
        result = _run(extract_cmd)
        news_path = result.stdout.strip()
        if not news_path:
            _run(cleanup_cmd)
            return None

        cat_cmd = f"cat '{news_path}'" if not news_path.endswith(".gz") else f"zcat '{news_path}'"
        content_result = _run(f"cd /tmp/_news_probe_{package} && {cat_cmd}")
        _run(cleanup_cmd)

        text = content_result.stdout.strip()
        return text or None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        try:
            _run(cleanup_cmd)
        except Exception:
            pass
        return None


# Debian changelog-tarzi girisin en ustundeki, en guncel maddeyi ayiklar:
# "pkg (version) urgency; ..." satirindan bir sonraki " -- " satirina kadar.
_ENTRY_RE = re.compile(r"^(.*?)\n\s*--\s", re.DOTALL)


def render_news_debian_chunk(package: str, news_text: str | None,
                             version: str, scraped_at: str,
                             max_chars: int = 1200) -> dict | None:
    """NEWS.Debian icerigini release-notes chunk'larla AYNI sekilde bicimlendirir.

    Yalniz EN GUNCEL girdi alinir (dosya genelde surum gecmisinin tamami --
    hepsini almak alakasiz eski bilgiyle bogar). news_text bossa None doner.
    """
    if not news_text:
        return None

    m = _ENTRY_RE.match(news_text)
    latest_entry = m.group(1).strip() if m else news_text[:max_chars]
    latest_entry = latest_entry[:max_chars]

    text = f"Debian maintainer notice for {package}: {latest_entry}"

    return {
        "id": f"news-debian_{version}_{package}",
        "text": text,
        "metadata": {
            "source_url": f"news-debian:{package}",
            "scraped_at": scraped_at,
            "section_title": "Debian NEWS.Debian",
            "version": version,
        },
    }
