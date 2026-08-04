"""M2 / Sprint 3 — Ubuntu çoklu sürüm scraper'ı.

Sürüme göre doğru URL ve doğru parser'ı seçer (yeni Sphinx / eski wiki).
"""

import json
import time
from pathlib import Path

from src.scraper.base_scraper import (
    fetch_page,
    save_raw_html,
    parse_release_notes,
    parse_wiki_release_notes,
)

CONFIG_PATH = Path("config/versions.json")

# format adı -> parser fonksiyonu
PARSERS = {
    "sphinx": parse_release_notes,
    "wiki": parse_wiki_release_notes,
}


def _load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def get_version_config(version: str) -> dict:
    """Sürümün {url, format} ayarını döner. Yoksa anlamlı hata fırlatır."""
    versions = _load_config()["versions"]
    if version not in versions:
        raise ValueError(
            f"Desteklenmeyen sürüm: {version!r}. "
            f"Desteklenenler: {list(versions)}"
        )
    return versions[version]


def scrape_version(version: str) -> list[dict]:
    """URL üret -> fetch -> kaydet -> doğru parser ile parse."""
    cfg = get_version_config(version)

    html = fetch_page(cfg["url"])
    if html is None:
        raise RuntimeError(f"Sayfa çekilemedi: {cfg['url']}")

    save_raw_html(html, version)

    parser = PARSERS[cfg["format"]]
    sections = parser(html, version=version, source_url=cfg["url"])

    if not sections:                                    # <-- EKLENEN
        print(f"[WARN] {version}: hiç bölüm ayrıştırılamadı — "
              f"sayfa yapısı değişmiş olabilir ({cfg['url']})")




    time.sleep(1)   # kibarlık
    return sections
