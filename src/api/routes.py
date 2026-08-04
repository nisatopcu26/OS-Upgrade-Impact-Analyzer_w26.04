"""M6 — API endpoint'leri.

Hata dürüstlüğü ilkesi: desteklenmeyen sürüm → 422, Ollama kapalı → 503.
API da "uydurmaz" — sorun neyse onu söyler.
"""

import time

import httpx
from fastapi import APIRouter, HTTPException

from config.settings import OLLAMA_BASE_URL
from src.agent.graph import analyze
from src.api.schemas import (
    AnalyzeRequest, AnalyzeResponse, ChainAnalyzeResponse, DetectResponse,
    PackagesResponse, VersionsResponse,
)
from src.detector.os_detector import detect_os
from src.detector.package_inventory import get_inventory
from src.remote.ssh_runner import validate_host
from src.upgrade_path.chain import analyze_chain
from src.upgrade_path.path import compute_path, lts_chain

router = APIRouter()


def _supported_versions() -> list[str]:
    # Zincir semantiğinin sahibi upgrade_path modülü — tek gerçek kaynak
    return lts_chain()


def _check_host_param(host: str | None) -> None:
    """Query'den gelen host da AYNI doğrulamadan geçer (enjeksiyon → 422)."""
    if host is not None and not validate_host(host):
        raise HTTPException(
            status_code=422,
            detail=f"Geçersiz host formatı: {host!r} "
                   "(beklenen: kullanici@ip-veya-hostname)")


@router.get("/detect", response_model=DetectResponse)
def detect(host: str | None = None):
    _check_host_param(host)
    # Erişilemeyen hedefte detect_os sözleşme gereği error alanıyla döner
    return detect_os(host=host)


@router.get("/packages", response_model=PackagesResponse)
def packages(host: str | None = None):
    _check_host_param(host)
    inv = get_inventory(host=host)
    return {
        "count": inv["count"],
        "source": inv["source"],
        "collected_at": inv["collected_at"],
        "sample": inv["packages"][:20],
        "error": inv.get("error"),
    }


@router.get("/versions", response_model=VersionsResponse)
def versions():
    return {"supported": _supported_versions()}


def _validate_versions(req: AnalyzeRequest) -> None:
    """422 matrisi — /analyze ve /analyze-chain ORTAK (tek gerçek kaynak)."""
    supported = _supported_versions()
    if req.target_version not in supported:
        raise HTTPException(
            status_code=422,
            detail=f"Desteklenmeyen hedef sürüm: {req.target_version!r}. "
                   f"Desteklenenler: {supported}")
    if req.current_version and req.current_version not in supported:
        raise HTTPException(
            status_code=422,
            detail=f"Desteklenmeyen mevcut sürüm: {req.current_version!r}. "
                   f"Desteklenenler: {supported}")
    # v2: downgrade/aynı sürüm dürüstçe reddedilir (YY.MM string sıralaması
    # doğru çalışır: "18.04" < "24.04"). current otomatik tespitteyse aynı
    # kontrol node_detect içinde yapılır (ValueError → 422).
    if req.current_version and req.target_version <= req.current_version:
        raise HTTPException(
            status_code=422,
            detail=f"Hedef sürüm ({req.target_version}) mevcut sürümden "
                   f"({req.current_version}) yeni olmalı — downgrade/aynı "
                   "sürüm desteklenmez.")


def _check_ollama() -> None:
    """LLM'e girmeden Ollama sağlığı — kapalıysa dürüst 503."""
    try:
        httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Ollama'ya ulaşılamıyor — LLM servisi kapalı görünüyor. "
                   "`ollama serve` çalışıyor mu?")


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_endpoint(req: AnalyzeRequest):
    _validate_versions(req)
    _check_ollama()

    t0 = time.time()
    try:
        report = analyze(
            target_version=req.target_version,
            current_version=req.current_version,
            packages=req.packages,
            host=req.host,
        )
    except ConnectionError as exc:
        # Uzak hedefe ulaşılamadı — LLM hiç çağrılmadan dürüst 502
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        # node_detect'in downgrade/aynı-sürüm kontrolü (otomatik tespit yolu)
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Zincir Aşama 1 — dürüst yol bilgisi: current rapor SONRASI kesin bellidir
    # (otomatik tespit yolu dahil). Çok-bacaklıysa raporun kapsam sınırı da
    # dürüstçe yazılır ("uydurma yok"un kapsam yüzü: neyi BİLMEDİĞİNİ söyle).
    path_info = compute_path(report["current_version"], req.target_version)
    if path_info["path"] and not path_info["is_direct"]:
        report["warnings"] = list(report.get("warnings", [])) + [
            f"Resmi upgrade yolu: {' → '.join(path_info['path'])} — doğrudan "
            f"atlanamaz. Bu rapor YALNIZCA {req.target_version} sürümünün "
            f"değişikliklerini kapsar; ara sürümlerin "
            f"({', '.join(path_info['skipped_intermediates'])}) değişiklikleri "
            "dahil DEĞİL."]

    return {**report, "upgrade_path": path_info,
            "duration_s": round(time.time() - t0, 1)}


@router.post("/analyze-chain", response_model=ChainAnalyzeResponse)
def analyze_chain_endpoint(req: AnalyzeRequest):
    """Zincir Aşama 2: resmi LTS yolunun her bacağını ayrı analiz eder.

    UZUN sürer (bacak başına ~1-2 dk; 18.04→24.04 = 3 bacak ≈ 5 dk) —
    v1 senkron (M6 kararıyla tutarlı; job-queue kapsam dışı, architecture.md).
    """
    _validate_versions(req)
    _check_ollama()

    current = req.current_version
    if not current:
        # /analyze'daki otomatik tespitle aynı UX; tespit edilemezse dürüst 502
        osinfo = detect_os(host=req.host)
        current = osinfo.get("version")
        if not current:
            raise HTTPException(
                status_code=502,
                detail=f"Mevcut sürüm tespit edilemedi: {osinfo.get('error')}")

    t0 = time.time()
    try:
        result = analyze_chain(current=current, target=req.target_version,
                               packages=req.packages, host=req.host)
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError as exc:
        # compute_path hatası (zincir dışı sürüm / downgrade) — /analyze simetriği
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {**result, "duration_s": round(time.time() - t0, 1)}
