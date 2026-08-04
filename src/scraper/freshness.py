"""M3.5 / Sprint 4 — Tazelik (freshness) ve cache katmanı.

Parse sonuçlarını data/processed/{version}.json olarak saklar.
Veri yoksa ya da bayatsa (TTL aşımı) otomatik yeniden scrape eder.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from config import settings
from src.scraper.ubuntu_scraper import scrape_version

PROCESSED_DIR = Path("data/processed")


def _processed_path(version: str) -> Path:
    return PROCESSED_DIR / f"{version}.json"


def save_processed(version: str, sections: list[dict], source_url: str) -> dict:
    """Bölümleri metadata'lı bir zarf içinde JSON olarak kaydeder."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "version": version,
        "source_url": source_url,
        "scraped_at": datetime.now().isoformat(),   # ISO 8601 zaman damgası
        "section_count": len(sections),
        "sections": sections,
    }
    _processed_path(version).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return data


def is_stale(scraped_at: str, ttl_seconds: float) -> bool:
    """scraped_at (ISO string) TTL süresini aştı mı?"""
    scraped_dt = datetime.fromisoformat(scraped_at)
    age = datetime.now() - scraped_dt
    return age > timedelta(seconds=ttl_seconds)


def get_version_data(version: str, ttl_seconds: float | None = None) -> dict:
    """Ana giriş noktası: taze cache varsa onu döner, yoksa/bayatsa yeniden çeker."""
    if ttl_seconds is None:
        ttl_seconds = settings.TTL_DAYS * 86400   # gün -> saniye

    path = _processed_path(version)

    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not is_stale(data["scraped_at"], ttl_seconds):
            print(f"[CACHE] {version} taze — cache'ten okundu (internete gidilmedi)")
            return data
        print(f"[STALE] {version} bayat — yeniden çekiliyor")
    else:
        print(f"[MISS]  {version} cache'te yok — çekiliyor")

    sections = scrape_version(version)
    source_url = sections[0]["source_url"] if sections else ""
    return save_processed(version, sections, source_url)


def get_versions_data(versions: list[str], ttl_seconds: float | None = None) -> dict:
    """Birden çok sürümü çeker; biri patlarsa diğerleri etkilenmez.

    Döner: {"ok": {version: data}, "failed": {version: hata_mesajı}}
    """
    ok, failed = {}, {}
    for version in versions:
        try:
            ok[version] = get_version_data(version, ttl_seconds)
        except Exception as e:
            failed[version] = f"{type(e).__name__}: {e}"
            print(f"[FAIL] {version} atlandı — {e}")

    print(f"\n[ÖZET] {len(ok)} başarılı, {len(failed)} başarısız")
    return {"ok": ok, "failed": failed}
