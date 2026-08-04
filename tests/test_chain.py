"""Zincir orkestrasyonu testleri — LLM/Chroma/ağ YOK.

analyze_fn ve corpus_fn enjekte edilir (projenin sayaç-enjeksiyonu deseni);
gerçek graph/Chroma yığını hiç import edilmez (chain.py lazy import).
"""

import pytest

from src.upgrade_path.chain import analyze_chain


def _fake_report(current: str, target: str) -> dict:
    return {"host": None, "current_version": current, "target_version": target,
            "summary": "s", "claims": [], "not_found_notes": [],
            "rejected_claims": [], "package_candidates": [],
            "affected_packages": [], "freshness": {}, "warnings": [],
            "stats": {"draft_claims": 0, "verified": 0, "rejected": 0,
                      "flagged": 0}}


def _recording_analyze(calls: list, fail_on_call: int | None = None):
    def _fake(target_version, current_version=None, packages=None, host=None):
        calls.append({"current": current_version, "target": target_version,
                      "packages": list(packages), "host": host})
        if fail_on_call is not None and len(calls) == fail_on_call:
            raise RuntimeError(f"bacak {len(calls)} kasıtlı patladı")
        return _fake_report(current_version, target_version)
    return _fake


NO_REMOVALS = lambda version: []          # noqa: E731 — boş korpus enjeksiyonu


def test_three_legs_called_in_order_with_correct_versions():
    calls = []
    result = analyze_chain("18.04", "24.04", packages=["php"],
                           corpus_fn=NO_REMOVALS,
                           analyze_fn=_recording_analyze(calls))
    assert [(c["current"], c["target"]) for c in calls] == [
        ("18.04", "20.04"), ("20.04", "22.04"), ("22.04", "24.04")]
    assert len(result["legs"]) == 3 and result["error"] is None
    assert result["upgrade_path"]["is_direct"] is False
    assert result["evolution_disclaimer"]        # model sınırı raporda yazılı


def test_leg2_receives_evolved_inventory():
    # 20.04 bacağında python2 açıkça kaldırılıyor → bacak 2 onu GÖRMEMELİ
    def corpus_fn(version):
        if version == "20.04":
            return [{"id": "20.04_py_0",
                     "text": "python2 has been removed from the archive."}]
        return []

    calls = []
    result = analyze_chain("18.04", "24.04", packages=["python2", "nginx"],
                           corpus_fn=corpus_fn,
                           analyze_fn=_recording_analyze(calls))
    assert calls[0]["packages"] == ["nginx", "python2"]   # bacağa GİREN envanter
    assert calls[1]["packages"] == ["nginx"]              # python2 düştü
    leg1 = result["legs"][0]
    assert [r["package"] for r in leg1["evolution"]["removed"]] == ["python2"]
    assert leg1["evolution"]["removed"][0]["chunk_id"] == "20.04_py_0"


def test_injected_packages_skip_inventory_read(monkeypatch):
    # packages verilmişse get_inventory HİÇ çağrılmamalı (lazy import edilen
    # modülün fonksiyonu patch'lenir — çağrılırsa test patlar)
    def _boom(**kwargs):
        raise AssertionError("get_inventory çağrılmamalıydı")
    monkeypatch.setattr("src.detector.package_inventory.get_inventory", _boom)
    result = analyze_chain("22.04", "24.04", packages=["php"],
                           corpus_fn=NO_REMOVALS,
                           analyze_fn=_recording_analyze([]))
    assert result["error"] is None


def test_partial_failure_returns_completed_legs_plus_error():
    calls = []
    result = analyze_chain("18.04", "24.04", packages=["php"],
                           corpus_fn=NO_REMOVALS,
                           analyze_fn=_recording_analyze(calls, fail_on_call=2))
    assert len(result["legs"]) == 1                       # tamamlanan bacak korunur
    assert result["error"]["leg"] == ["20.04", "22.04"]   # hata dürüstçe işaretli
    assert "kasıtlı" in result["error"]["detail"]
    assert len(calls) == 2                                # bacak 3'e hiç geçilmedi


def test_first_leg_failure_reraises():
    with pytest.raises(RuntimeError):
        analyze_chain("18.04", "24.04", packages=["php"],
                      corpus_fn=NO_REMOVALS,
                      analyze_fn=_recording_analyze([], fail_on_call=1))


def test_invalid_path_raises_value_error():
    with pytest.raises(ValueError):
        analyze_chain("24.04", "18.04", packages=[],     # downgrade
                      corpus_fn=NO_REMOVALS, analyze_fn=_recording_analyze([]))


def test_per_leg_duration_injected():
    result = analyze_chain("20.04", "24.04", packages=[],
                           corpus_fn=NO_REMOVALS,
                           analyze_fn=_recording_analyze([]))
    assert all(isinstance(leg["report"]["duration_s"], float)
               for leg in result["legs"])
