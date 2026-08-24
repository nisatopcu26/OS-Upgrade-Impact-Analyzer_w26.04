"""M9 (26.04 turu) -- Apt Breaks/Conflicts/Replaces/Provides: ikinci kanit
katmani. Release notes'un anlatmadigi ama apt paket metadata'sinda birebir
var olan iliskileri (ornegin Samba'nin samba-vfs-modules'u Replaces etmesi)
yakalamak icin. Deterministik -- LLM yok.

Cift modlu (proje kurali): host=None -> yerel, host=str -> SSH (agentless).
"""

import re
import subprocess

_FIELDS = ("Breaks", "Conflicts", "Replaces", "Provides")
_FIELD_RE = re.compile(r"^(" + "|".join(_FIELDS) + r"):\s*(.+)$")


def get_apt_relations(package: str, host: str | None = None,
                      timeout: int = 15) -> dict:
    """Bir paketin Breaks/Conflicts/Replaces/Provides alanlarini doner.

    Bos sozluk = ya paket bulunamadi ya da hicbir iliskisel alani yok
    (ikisi de meşru durumlar -- sessizce ayirt edilmez, cagiran taraf
    'veri yok' olarak yorumlar, asla uydurmaz).
    """
    cmd = f"apt-cache show {package} 2>/dev/null | head -30"
    try:
        if host:
            result = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", host, cmd],
                capture_output=True, text=True, timeout=timeout,
            )
        else:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout,
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {}

    relations = {}
    for line in result.stdout.splitlines():
        m = _FIELD_RE.match(line)
        if m and m.group(1) not in relations:   # ilk gorulen deger (Package: bloklari tekrarlanabilir)
            relations[m.group(1)] = m.group(2).strip()
    return relations


def render_apt_relations_chunk(package: str, relations: dict,
                               version: str, scraped_at: str) -> dict | None:
    """Iliski sozlugunu, release-notes chunk'larla AYNI sekilde (id, text,
    metadata) bicimlendirir -- grounding katmani ikisini ayirt etmeden
    islesin diye. source_url'deki 'apt-cache:' oneki, bu bilginin release
    notes'tan DEGIL apt metadata'sindan geldigini serffaf sekilde isaretler.

    relations bossa None doner -- uydurma icerik oluşturulmaz.
    """
    if not relations:
        return None

    parts = [f"APT package metadata for {package}:"]
    for field in _FIELDS:
        if field in relations:
            parts.append(f"{field} {relations[field]}.")
    text = " ".join(parts)

    return {
        "id": f"apt-relations_{version}_{package}",
        "text": text,
        "metadata": {
            "source_url": f"apt-cache:{package}",
            "scraped_at": scraped_at,
            "section_title": "APT Package Relations",
            "version": version,
        },
    }
