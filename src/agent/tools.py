"""M4 / A2 — Agent tool'ları.

Mevcut deterministik modülleri agent'ın kullanacağı tek tip arayüze sarar.
"Scraper agent'ın tool'u" mimarisi fiilen burada: ensure_fresh_data,
freshness zinciri üzerinden veri bayatsa OTOMATİK yeniden scrape eder —
'veri bayat mı?' kararı agent akışının içinde çözülür.
"""

import json
from pathlib import Path

from config.settings import TOP_K
from src.detector.os_detector import detect_os
from src.detector.package_inventory import get_inventory
from src.rag.vector_store import search
from src.scraper.freshness import get_version_data

PROCESSED_DIR = Path("data/processed")


def detect_current_os(host: str | None = None) -> dict:
    """Hedef sistemi tespit eder (M1; host verilirse SSH ile uzaktan)."""
    return detect_os(host=host)


def get_installed_packages(host: str | None = None) -> dict:
    """Kullanıcının elle kurduğu paketler (Faz 2; host verilirse uzaktan)."""
    return get_inventory(host=host)


def ensure_fresh_data(version: str) -> dict:
    """Sürüm verisini taze garanti eder; bayatsa yeniden scrape (M2+M3.5).

    Ağ çökerse ve diskte eski veri varsa: bayat veriyle devam eder ama
    bunu açıkça işaretler (_stale_fallback) — sessizce taze gibi davranmaz.
    """
    try:
        data = get_version_data(version)
        data["_stale_fallback"] = False
        return data
    except Exception as exc:
        path = PROCESSED_DIR / f"{version}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_stale_fallback"] = True
            data["_error"] = str(exc)
            return data
        raise


def search_release_notes(query: str, version: str, top_k: int = TOP_K) -> list[dict]:
    """RAG araması (M3) — hedef sürümle filtreli."""
    return search(query, top_k=top_k, version=version)
