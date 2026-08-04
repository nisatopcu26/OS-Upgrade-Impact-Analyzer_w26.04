"""Zincir upgrade — Aşama 1: resmi LTS yolunun deterministik hesabı.

Ubuntu'nun resmi upgrade yolu sıralı LTS zinciridir (18.04→20.04→22.04→24.04);
`do-release-upgrade` atlama yapmaz. Bu modül yolu MEKANİK hesaplar — LLM yok,
tahmin yok: zincir `config/versions.json`'dan türetilir (tek gerçek kaynak;
yeni LTS eklenince tek dosya değişir).

DİKKAT: Bu modül ağır bağımlılık import ETMEZ (grounding/embeddings yok) —
Streamlit UI compute_path'i doğrudan import eder, açılışı yavaşlatmamalı.
"""

import json
from pathlib import Path

# app.py'nin hosts.json deseni: cwd'den bağımsız, dosyaya göre mutlak yol
_VERSIONS_PATH = Path(__file__).resolve().parents[2] / "config" / "versions.json"


def lts_chain() -> list[str]:
    """versions.json anahtarları, sıralı = resmi LTS zinciri (YY.MM string sort).

    Okunamazsa RuntimeError — sessiz hardcoded fallback YOK: bayat gömülü liste,
    yeni eklenen bir LTS'i sessizce gizlerdi ("uydurma yok" ilkesinin config yüzü).
    """
    try:
        data = json.loads(_VERSIONS_PATH.read_text(encoding="utf-8"))
        chain = sorted(data["versions"])
    except (OSError, ValueError, KeyError) as exc:
        raise RuntimeError(f"versions.json okunamadı: {exc}") from exc
    if not chain:
        raise RuntimeError("versions.json boş — LTS zinciri türetilemedi")
    return chain


def compute_path(current: str, target: str,
                 chain: list[str] | None = None) -> dict:
    """current→target arası resmi upgrade yolu.

    chain=None → lts_chain() (testler sahte zincir enjekte edebilir —
    projenin sayaç-enjeksiyonu deseni). Hata da dict döner (exception değil):
    çağıranlar (UI/routes) akışı bozmadan dürüst mesaj gösterebilsin.

    OK:   {"path": ["18.04","20.04","22.04","24.04"],
           "legs": [("18.04","20.04"), ("20.04","22.04"), ("22.04","24.04")],
           "is_direct": False, "skipped_intermediates": ["20.04","22.04"],
           "error": None}
    Hata: {"path": None, "legs": [], "is_direct": False,
           "skipped_intermediates": [], "error": "..."}
    """
    if chain is None:
        chain = lts_chain()

    def _err(msg: str) -> dict:
        return {"path": None, "legs": [], "is_direct": False,
                "skipped_intermediates": [], "error": msg}

    if current not in chain:
        return _err(f"sürüm LTS zincirinde değil: {current!r} "
                    f"(zincir: {chain})")
    if target not in chain:
        return _err(f"sürüm LTS zincirinde değil: {target!r} "
                    f"(zincir: {chain})")
    i, j = chain.index(current), chain.index(target)
    if j <= i:
        return _err(f"hedef ({target}) mevcut sürümden ({current}) yeni olmalı "
                    "— downgrade/aynı sürüm desteklenmez")

    path = chain[i:j + 1]
    legs = list(zip(path, path[1:]))
    return {
        "path": path,
        "legs": legs,
        "is_direct": len(legs) == 1,
        "skipped_intermediates": path[1:-1],   # rapora dahil OLMAYAN ara sürümler
        "error": None,
    }
