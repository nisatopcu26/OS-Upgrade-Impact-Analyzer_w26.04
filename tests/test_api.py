"""API endpoint testleri — İLK TestClient suite'i (zincir işiyle geldi).

LLM/Chroma/ağ YOK: `routes.analyze` (ve Sprint 4'te `routes.analyze_chain`)
monkeypatch'lenir; Ollama ön-kontrolündeki httpx.get de sahtelenir. Amaç
endpoint SÖZLEŞMESİNİ kilitlemek: doğrulama matrisi, hata eşlemesi, yanıt şeması.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api import routes
from src.api.main import app

client = TestClient(app)


def _fake_report(current: str, target: str) -> dict:
    """analyze()'ın döndürdüğü rapor sözleşmesinin asgari örneği."""
    return {"host": None, "current_version": current, "target_version": target,
            "summary": "test özeti", "claims": [], "not_found_notes": [],
            "rejected_claims": [], "package_candidates": [],
            "affected_packages": [], "freshness": {}, "warnings": [],
            "stats": {"draft_claims": 0, "verified": 0, "rejected": 0,
                      "flagged": 0}}


@pytest.fixture
def ollama_up(monkeypatch):
    monkeypatch.setattr(routes.httpx, "get", lambda *a, **k: None)


@pytest.fixture
def fake_analyze(monkeypatch):
    calls = []

    def _fake(target_version, current_version=None, packages=None, host=None):
        calls.append({"target": target_version, "current": current_version,
                      "packages": packages, "host": host})
        return _fake_report(current_version or "22.04", target_version)

    monkeypatch.setattr(routes, "analyze", _fake)
    return calls


# --- Zincir Aşama 1: /analyze yanıtında upgrade_path -----------------------

def test_analyze_includes_upgrade_path_multi_leg(ollama_up, fake_analyze):
    r = client.post("/analyze", json={"target_version": "24.04",
                                      "current_version": "18.04"})
    assert r.status_code == 200
    body = r.json()
    up = body["upgrade_path"]
    assert up["path"] == ["18.04", "20.04", "22.04", "24.04"]
    assert up["is_direct"] is False
    assert up["skipped_intermediates"] == ["20.04", "22.04"]
    # kapsam sınırı raporun KENDİ içinde de yazılı (dürüstlük)
    assert any("Resmi upgrade yolu" in w for w in body["warnings"])


def test_analyze_single_leg_direct_no_scope_warning(ollama_up, fake_analyze):
    r = client.post("/analyze", json={"target_version": "24.04",
                                      "current_version": "22.04"})
    assert r.status_code == 200
    body = r.json()
    assert body["upgrade_path"]["is_direct"] is True
    assert body["upgrade_path"]["legs"] == [["22.04", "24.04"]]
    # tek bacakta gereksiz gürültü yok
    assert not any("Resmi upgrade yolu" in w for w in body["warnings"])


def test_analyze_ollama_down_503(monkeypatch, fake_analyze):
    def _raise(*a, **k):
        raise httpx.ConnectError("bağlantı yok")
    monkeypatch.setattr(routes.httpx, "get", _raise)
    r = client.post("/analyze", json={"target_version": "24.04",
                                      "current_version": "22.04"})
    assert r.status_code == 503
    assert fake_analyze == []          # LLM akışı hiç çağrılmadı


def test_analyze_unsupported_target_422(ollama_up, fake_analyze):
    r = client.post("/analyze", json={"target_version": "25.04"})
    assert r.status_code == 422
    assert fake_analyze == []


def test_analyze_downgrade_422(ollama_up, fake_analyze):
    r = client.post("/analyze", json={"target_version": "20.04",
                                      "current_version": "24.04"})
    assert r.status_code == 422
    assert fake_analyze == []


# --- Zincir Aşama 2: /analyze-chain -----------------------------------------

def _fake_chain_result(current: str, target: str) -> dict:
    legs = [{"from_version": "22.04", "to_version": "24.04",
             "inventory_size": 1, "inventory": ["php"],
             "evolution": {"removed": [{"package": "pptpd",
                                        "chunk_id": "24.04_pptpd-removed_0",
                                        "quote": "pptpd ... removed"}],
                           "renamed": []},
             "report": {**_fake_report("22.04", "24.04"), "duration_s": 1.0}}]
    return {"host": None, "current_version": current, "target_version": target,
            "upgrade_path": {"path": [current, target],
                             "legs": [(current, target)], "is_direct": True,
                             "skipped_intermediates": [], "error": None},
            "legs": legs, "evolution_disclaimer": "model sınırı",
            "warnings": [], "error": None}


@pytest.fixture
def fake_chain(monkeypatch):
    calls = []

    def _fake(current, target, packages=None, host=None):
        calls.append({"current": current, "target": target,
                      "packages": packages, "host": host})
        return _fake_chain_result(current, target)

    monkeypatch.setattr(routes, "analyze_chain", _fake)
    return calls


def test_chain_happy_path_response_shape(ollama_up, fake_chain):
    r = client.post("/analyze-chain", json={"target_version": "24.04",
                                            "current_version": "22.04"})
    assert r.status_code == 200
    body = r.json()
    assert body["duration_s"] >= 0
    assert body["legs"][0]["evolution"]["removed"][0]["package"] == "pptpd"
    assert body["evolution_disclaimer"]
    assert fake_chain[0] == {"current": "22.04", "target": "24.04",
                             "packages": None, "host": None}


def test_chain_unsupported_target_422(ollama_up, fake_chain):
    r = client.post("/analyze-chain", json={"target_version": "25.04"})
    assert r.status_code == 422 and fake_chain == []


def test_chain_downgrade_422(ollama_up, fake_chain):
    r = client.post("/analyze-chain", json={"target_version": "18.04",
                                            "current_version": "24.04"})
    assert r.status_code == 422 and fake_chain == []


def test_chain_ollama_down_503(monkeypatch, fake_chain):
    def _raise(*a, **k):
        raise httpx.ConnectError("bağlantı yok")
    monkeypatch.setattr(routes.httpx, "get", _raise)
    r = client.post("/analyze-chain", json={"target_version": "24.04",
                                            "current_version": "22.04"})
    assert r.status_code == 503 and fake_chain == []


def test_chain_injection_host_422(ollama_up, fake_chain):
    # SSH argüman enjeksiyonu zincir endpoint'inde de API sınırında ölür
    r = client.post("/analyze-chain",
                    json={"target_version": "24.04", "current_version": "22.04",
                          "host": "-oProxyCommand=x"})
    assert r.status_code == 422 and fake_chain == []


def test_chain_partial_error_passes_through(ollama_up, monkeypatch):
    partial = _fake_chain_result("22.04", "24.04")
    partial["error"] = {"leg": ["20.04", "22.04"], "detail": "Ollama koptu"}
    monkeypatch.setattr(routes, "analyze_chain", lambda **kw: partial)
    r = client.post("/analyze-chain", json={"target_version": "24.04",
                                            "current_version": "22.04"})
    # kısmi sonuç: HTTP 200 + error alanı dolu (D6 sözleşmesi)
    assert r.status_code == 200
    assert r.json()["error"]["detail"] == "Ollama koptu"
