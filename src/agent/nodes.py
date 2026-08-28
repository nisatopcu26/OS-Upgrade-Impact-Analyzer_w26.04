"""M4 / A3 — LangGraph node'ları.

Akış:  detect → refresh → retrieve_general → package_intersect → draft_report
Her node state sözlüğünü alır, değişen alanları döner. LLM yalnızca
draft_report'ta devreye girer; öncesi tamamen deterministik.
"""

import json
import re

from langchain_ollama import ChatOllama

from config.settings import LLM_MODEL, OLLAMA_BASE_URL
from src.agent.tools import (
    detect_current_os, ensure_fresh_data, get_installed_packages,
    search_release_notes,
)
from src.detector.apt_relations import get_apt_relations, render_apt_relations_chunk
from src.detector.news_debian import get_news_debian, render_news_debian_chunk
from src.rag.vector_store import get_collection, build_index
from src.remote.ssh_runner import is_reachable

import json
from datetime import datetime, timezone
from pathlib import Path as _Path

_HOSTS_PATH = _Path(__file__).resolve().parents[2] / "config" / "hosts.json"


def _reference_host_for(version: str) -> str | None:
    """config/hosts.json'dan hedef surumun referans VM'ini bulur (2. kanit
    katmani icin -- analiz edilen sistem henuz o surume gecmedigi icin,
    hedefin paket iliskilerini yalniz kendi VM'inde gorebiliriz).
    Bulunamazsa/dosya yoksa None -- katman sessizce atlanir, cokmez."""
    try:
        hosts = json.loads(_HOSTS_PATH.read_text(encoding="utf-8"))["hosts"]
        entry = next((h for h in hosts if version in h["label"]), None)
        return entry["host"] if entry else None
    except (FileNotFoundError, KeyError, StopIteration):
        return None

# Hedef sürümün genel değişikliklerini toplayan sabit sorgular (İngilizce —
# kilitli karar: veriler ve embedding modeli İngilizce).
GENERAL_QUERIES = [
    "known issues and bugs in this release",
    "new features and major changes",
    "removed or deprecated packages and features",
    "upgrade instructions and requirements",
]

MAX_PACKAGE_CANDIDATES = 15   # LLM bağlamını şişirmemek için üst sınır

# Senaryo-bazlı model override (deney amaçlı, S6): belirli versiyon
# çiftlerinde varsayılan LLM_MODEL yerine farklı bir model kullanılır.
# Boş bırakılırsa (silinirse) sistem her zaman LLM_MODEL kullanır.
MODEL_OVERRIDES = {
    ("24.04", "26.04"): "llama3.1:8b",
}


import re


def _version_key(version: str) -> tuple:
    """Surum string'inden sayisal parcalari cikarip tuple olarak doner --
    format bagimsiz dogru karsilastirma icin ("24.04" -> (24, 4),
    "rocky-10.2" -> (10, 2), "rocky-9.8" -> (9, 8)). Sayi bulunamazsa
    (0,) doner -- karsilastirma cokmuyor, sadece en dusuk siraya duser.
    """
    numbers = re.findall(r"\d+", version)
    return tuple(int(n) for n in numbers) if numbers else (0,)


def node_detect(state: dict) -> dict:
    """Hedef sistemin sürümü (verilmediyse) ve paket envanteri (verilmediyse)
    tespit edilir — state'te host varsa SSH ile uzaktan (roadmap v2 / S4).

    packages dışarıdan enjekte edilebilir — M8'de sahte envanterle senaryo
    koşabilmek için.
    """
    host = state.get("host")
    out = {}
    if not state.get("current_version"):
        osinfo = detect_current_os(host=host)
        if not osinfo.get("version"):
            where = f" (host: {host})" if host else ""
            raise RuntimeError(
                f"Sistem tespit edilemedi{where}: {osinfo.get('error')}")
        out["current_version"] = osinfo["version"]
    if state.get("packages") is None:
        inv = get_installed_packages(host=host)
        out["packages"] = inv["packages"]

    # Downgrade/aynı sürüm kontrolü — current otomatik tespit edildiyse ancak
    # burada bilinebilir (API bunu 422'ye çevirir).
    # 2026-08-28 DUZELTME: duz string karsilastirmasi ("target <= current")
    # yalniz Ubuntu'nun YY.MM formatinda (yil basta oldugu icin) tesadufen
    # dogruydu -- Rocky'nin major.minor formatinda ("rocky-10.2" vs
    # "rocky-9.8") karakter-bazli karsilastirma YANLIS sonuc veriyordu
    # ("1" < "9" oldugu icin 10.2, 9.8'den kucuk sayiliyordu). Gercek RHEL
    # 9->10 senaryosu test edilirken bulundu. Simdi sayisal parcalar
    # cikarilip tuple olarak karsilastiriliyor -- format bagimsiz.
    current = out.get("current_version") or state.get("current_version")
    target = state.get("target_version")
    if current and target and _version_key(target) <= _version_key(current):
        raise ValueError(
            f"Hedef sürüm ({target}) mevcut sürümden "
            f"({current}) yeni olmalı — downgrade/aynı sürüm desteklenmez.")
    return out


def node_refresh(state: dict) -> dict:
    """Her iki sürümün verisini taze garanti eder (bayatsa otomatik scrape)."""
    freshness, warnings = {}, list(state.get("warnings", []))
    for version in (state["current_version"], state["target_version"]):
        data = ensure_fresh_data(version)
        freshness[version] = {
            "scraped_at": data.get("scraped_at", ""),
            "stale_fallback": data.get("_stale_fallback", False),
        }
        if data.get("_stale_fallback"):
            warnings.append(
                f"{version}: ağ hatası nedeniyle bayat veri kullanıldı "
                f"({data.get('_error', '')})"
            )
        existing = get_collection().get(where={"version": version}, limit=1)
        if not existing["ids"]:
            print(f"[AUTO-INDEX] {version}: chunk bulunamadı, indeksleniyor...")
            build_index(versions=[version])

    return {"freshness": freshness, "warnings": warnings}


def node_retrieve_general(state: dict) -> dict:
    """Hedef sürümün genel değişiklik chunk'larını toplar (id bazında tekilleştirilmiş)."""
    seen, chunks = set(), []
    for query in GENERAL_QUERIES:
        for hit in search_release_notes(query, state["target_version"], top_k=4):
            if hit["id"] not in seen:
                seen.add(hit["id"])
                chunks.append(hit)
    # En alakalılar önce; LLM bağlamını sınırla
    chunks.sort(key=lambda h: h["similarity"], reverse=True)
    return {"general_chunks": chunks[:10]}


def node_package_intersect(state: dict) -> dict:
    """İki aşamalı kesiştirme (kilitli karar):

    1) UCUZ sözcüksel eleme: hedef sürümün TÜM chunk metinlerinde kurulu paket
       adlarını kelime-sınırıyla ara → yüzlerce paket saniyeler içinde ~10-20
       adaya iner (LLM/embedding maliyeti yok).
    2) Sadece adaylar için hedefli RAG araması → paket başına en alakalı chunk'lar.
    """
    target = state["target_version"]
    data = get_collection().get(where={"version": target}, include=["documents"])
    corpus = "\n".join(data["documents"]).lower()

    candidates = []
    for pkg in state["packages"]:
        if len(pkg) < 3:            # 'bc' gibi 2 harfliler yanlış eşleşmeye açık
            continue
        if re.search(rf"\b{re.escape(pkg.lower())}\b", corpus):
            candidates.append(pkg)
    candidates = candidates[:MAX_PACKAGE_CANDIDATES]

    package_hits = {}
    for pkg in candidates:
        hits = search_release_notes(
            f"{pkg} package changes removal deprecation", target, top_k=2)
        # Sözcüksel doğrulama: dönen chunk gerçekten bu paketi anıyor mu?
        hits = [h for h in hits
                if re.search(rf"\b{re.escape(pkg.lower())}\b", h["text"].lower())]
        if hits:
            package_hits[pkg] = hits

    # 2. kanit katmani (2026-08-21 turu): apt Breaks/Conflicts/Replaces/
    # Provides -- release notes'un anlatmadigi ama apt metadata'sinda
    # birebir var olan iliskileri yakalar (orn. samba-vfs-modules Replaces).
    # Referans VM erisilemezse SESSIZCE atlanir (cokmez, uydurmaz) -- ama
    # bu turu warnings'e bir kez isaretleriz.
    apt_warning_added = False
    ref_host = _reference_host_for(target)
    if ref_host and is_reachable(ref_host):
        scraped_at = datetime.now(timezone.utc).isoformat()
        for pkg in candidates:
            relations = get_apt_relations(pkg, host=ref_host)
            chunk = render_apt_relations_chunk(pkg, relations, target, scraped_at)
            if chunk:
                package_hits.setdefault(pkg, []).append(chunk)

            # 3. kanit katmani (2026-08-21 turu): Debian bakim notlari --
            # dogal dil, release-notes'a en yakin format. apt-relations'tan
            # ayri denendi cunku indirme/cikarma daha yavas -- yalniz
            # candidates icin (en fazla 15 paket) calisir.
            news = get_news_debian(pkg, host=ref_host)
            news_chunk = render_news_debian_chunk(pkg, news, target, scraped_at)
            if news_chunk:
                package_hits.setdefault(pkg, []).append(news_chunk)
    elif ref_host:
        apt_warning_added = True

    result = {"package_candidates": candidates, "package_hits": package_hits}
    if apt_warning_added:
        result["_apt_relations_unreachable"] = ref_host
    return result



def _format_sources(chunks: list[dict]) -> str:
    return "\n\n".join(f"[{c['id']}]\n{c['text']}" for c in chunks)


PROMPT_TEMPLATE = """You are an OS upgrade impact analyst. A user is upgrading \
Ubuntu {current} to Ubuntu {target}.

STRICT RULES:
- Use ONLY the sources below. Do not use any outside knowledge.
- Every claim MUST cite at least one source id (the [id] shown above each source).
- If the sources do not support a statement, DO NOT make it.
- Write in English. Be specific and factual.
- Some sources are labeled "APT package metadata" (id starts with apt-relations_).
  These list Breaks/Conflicts/Replaces/Provides relationships that are NOT
  mentioned in release notes but indicate real compatibility issues. When such
  a source is present for a package, write a claim about it (e.g. what it
  breaks or replaces), citing that source id — this is important, high-value
  information the release notes alone do not capture.

SOURCES (release notes of Ubuntu {target}):
{general_sources}

SOURCES ABOUT PACKAGES INSTALLED ON THE USER'S MACHINE:
{package_sources}

The user has these packages installed that MAY be affected: {candidates}

Produce JSON exactly in this schema:
{{"summary": "2-3 sentence overview of the upgrade impact",
  "claims": [
    {{"text": "one specific factual statement",
      "chunk_ids": ["id-from-sources"],
      "category": "package" | "general" | "known_issue",
      "affected_package": "package-name-or-null"}}
  ]}}

Write 6-14 claims. Prioritize: (1) user's affected packages, (2) known issues,
(3) major general changes."""


def node_draft_report(state: dict) -> dict:
    """LLM (settings.LLM_MODEL — varsayılan qwen2.5:7b, kilitli karar; A/B için
    env ile değiştirilebilir) kaynaklara dayalı, chunk_id atıflı taslak üretir."""
    package_chunks = [h for hits in state.get("package_hits", {}).values() for h in hits]

    prompt = PROMPT_TEMPLATE.format(
        current=state["current_version"],
        target=state["target_version"],
        general_sources=_format_sources(state.get("general_chunks", [])),
        package_sources=_format_sources(package_chunks) or "(none found)",
        candidates=", ".join(state.get("package_hits", {})) or "(none matched)",
    )

    model_name = MODEL_OVERRIDES.get((state["current_version"], state["target_version"]), LLM_MODEL)
    llm = ChatOllama(model=model_name, base_url=OLLAMA_BASE_URL,
                     temperature=0, format="json", num_ctx=8192, num_predict=1600)
    response = llm.invoke(prompt)

    try:
        draft = json.loads(response.content)
    except json.JSONDecodeError:
        draft = {"summary": "", "claims": []}

    claims = [c for c in draft.get("claims", []) if isinstance(c, dict)]
    return {"draft_summary": draft.get("summary", ""), "draft_claims": claims, "used_model": model_name}
