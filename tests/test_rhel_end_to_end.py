"""2026-08-27 (RHEL-ailesi genislemesi) — projenin ASIL urununun (kaynak
gosteren rapor uretimi) Rocky Linux'a karsi uctan uca calistigini dogrular.

test_rhel_family.py'den ayri tutulur: bu test cok daha pahali (embedding
modeli + LLM cagrisi gerektirir), test_remote_lab.py/test_rhel_family.py
ise deterministik, hizli testlerdir.

Kullanim:
  pytest tests/test_rhel_end_to_end.py -v
"""

import json
from functools import lru_cache
from pathlib import Path

import pytest

from src.agent.graph import analyze
from src.remote.ssh_runner import is_reachable

pytestmark = pytest.mark.lab

_HOSTS = json.loads(
    (Path(__file__).resolve().parents[1] / "config" / "hosts.json")
    .read_text(encoding="utf-8"))["hosts"]


@lru_cache(maxsize=None)
def _reachable(host: str) -> bool:
    return is_reachable(host)


def _rocky_host() -> str:
    entry = next(h for h in _HOSTS if "Rocky" in h["label"])
    return entry["host"]


def test_analyze_produces_grounded_report_for_rocky():
    """analyze(), Rocky 10.0->10.2 senaryosunda gercek, kaynakli bir rapor
    uretir -- hicbir RHEL-ozel kod degisikligi olmadan calisan mimarinin
    NIHAI kaniti (sadece tespit/RAG degil, tam urun)."""
    host = _rocky_host()
    if not _reachable(host):
        pytest.skip(f"lab VM kapali/erisilemez: {host}")

    report = analyze(
        target_version="rocky-10.2",
        current_version="rocky-10.0",
        host=host,
    )

    # Sozlesme: rapor sozlugunun temel alanlari
    assert report["target_version"] == "rocky-10.2"
    assert report["current_version"] == "rocky-10.0"
    assert report["summary"]
    assert len(report["claims"]) > 0

    # En az bir iddia GERCEKTEN Rocky chunk'ina atif yapmali (mock/bos
    # degil, gercek RAG entegrasyonunun kaniti)
    all_chunk_ids = [cid for c in report["claims"] for cid in c["chunk_ids"]]
    assert any(cid.startswith("rocky-10.2_") for cid in all_chunk_ids)

    # Her iddia grounding sozlesmesine uymali
    for claim in report["claims"]:
        assert "support_score" in claim
        assert "sources" in claim
        assert "flags" in claim
        assert claim["support_score"] >= 0


def test_grounding_rejects_hallucinated_claims_on_rocky_content():
    """M8-tarzi adversarial test: grounding katmani, GERCEK Rocky chunk'larina
    karsi ATFEDILEN ama uydurma olan iddialari da dogru yakalar -- sistem
    kusursuz veriye degil, gercekten calisan bir doğrulamaya sahip."""
    from src.agent.grounding import verify_claims
    from src.agent.tools import search_release_notes

    entry = _rocky_host()
    if not _reachable(entry):
        pytest.skip(f"lab VM kapali/erisilemez: {entry}")

    real_hits = search_release_notes("chrony kernel updates", "rocky-10.2", top_k=5)
    assert real_hits, "gercek chunk bulunamadi, test kurulamiyor"

    fake_claims = [
        {"text": "This is a completely unsourced claim with no citation.",
         "chunk_ids": [], "category": "general", "affected_package": None},
        {"text": "Rocky Linux 10.2 includes a new feature called QuantumSync.",
         "chunk_ids": ["rocky-10.2_nonexistent-fake-section_0"],
         "category": "general", "affected_package": None},
        {"text": "PostgreSQL was completely removed from Rocky Linux 10.2 and is no longer available.",
         "chunk_ids": [real_hits[0]["id"]],
         "category": "package", "affected_package": "postgresql"},
    ]

    verified, rejected = verify_claims(
        fake_claims, real_hits,
        allowed_terms=("rocky-10.0", "rocky-10.2"),
    )

    assert len(verified) == 0
    assert len(rejected) == 3
    reasons = {r["reject_reason"] for r in rejected}
    assert "no_source_cited" in reasons
    assert "unknown_chunk_id" in reasons
    assert "unverified_entity" in reasons
