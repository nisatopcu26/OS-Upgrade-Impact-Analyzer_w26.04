"""S5 (update_plan_3) — kabul matrisi koşucusu: 6 senaryo × 2 konfig.

Konfigürasyonlar (LLM sabit: varsayılan qwen2.5:7b — kilitli karar):
  eski : EMBEDDING_MODEL=MiniLM + SIMILARITY_THRESHOLD=0.30 (env override,
         koleksiyon+önek profilden otomatik izler — S1 mekanizması)
  yeni : varsayılanlar (bge-small + 0.60, S2 flip)

Senaryolar: 3 M8 (lokal, enjekte envanter — ab_llm.py ile aynı listeler)
          + 3 SSH (config/hosts.json lab VM'leri; koşudan önce erişim kontrolü).

İki kolon da AYNI kodda koşar (S3 sözcükseli dahil) → tek değişken
embedding+eşik. Rollback kriterleri update_plan_3.md'de koşudan ÖNCE yazılı.

Kullanım:
  .venv/bin/python tests/matrix_s5.py                # 12 koşu (M8 + SSH)
  .venv/bin/python tests/matrix_s5.py --skip-ssh    # yalnız M8 (6 koşu)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
OUT_DIR = BASE / "docs" / "s5-matrix"
FROZEN_INV = BASE.parent / "rag_layer_bench" / "data" / "inventory_real.json"

CONFIGS = {
    "eski": {"EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2",
             "SIMILARITY_THRESHOLD": "0.30"},
    "yeni": {},   # varsayılanlar (bge-small + 0.60)
}

M8_SCENARIOS = {
    "m8_2204_2404_real": {"current": "22.04", "target": "24.04", "packages": "REAL"},
    "m8_2004_2204_server": {"current": "20.04", "target": "22.04",
                            "packages": ["php", "php-fpm", "postgresql", "mysql-server",
                                         "docker.io", "nginx", "redis-server", "haproxy",
                                         "openssh-server", "certbot"]},
    "m8_1804_2004_legacy": {"current": "18.04", "target": "20.04",
                            "packages": ["python2", "php", "chrony", "corosync",
                                         "samba", "ntp", "apache2", "mysql-server"]},
}

# SSH senaryoları: hosts.json etiketindeki sürümden hedef LTS+1 (scenario-results
# düzeni: 22.04→24.04, 20.04→22.04, 18.04→20.04; 24.04 VM'inin hedefi yok)
SSH_TARGETS = {"22.04": "24.04", "20.04": "22.04", "18.04": "20.04"}

WORKER = r"""
import json, sys, time
sys.path.insert(0, {base!r})
from src.agent.graph import analyze
from config.settings import EMBEDDING_MODEL, SIMILARITY_THRESHOLD, COLLECTION
t0 = time.perf_counter()
try:
    report = analyze({target!r}, current_version={current!r},
                     packages={packages!r}, host={host!r})
    out = {{"ok": True, "seconds": round(time.perf_counter() - t0, 1),
           "config_seen": {{"embedding": EMBEDDING_MODEL,
                           "threshold": SIMILARITY_THRESHOLD,
                           "collection": COLLECTION}},
           "model_field": report.get("model"),
           "draft": report.get("stats", {{}}).get("draft_claims"),
           "verified": len(report.get("claims", [])),
           "rejected": len(report.get("rejected_claims", [])),
           "reject_reasons": [c.get("reject_reason") for c in report.get("rejected_claims", [])],
           "rejected_texts": [(c.get("text") or "")[:100] for c in report.get("rejected_claims", [])],
           "flags": sum(len(c.get("flags") or []) for c in report.get("claims", [])),
           "flag_terms": [f.get("term") for c in report.get("claims", [])
                          for f in (c.get("flags") or [])],
           "support_scores": [c.get("support_score") for c in report.get("claims", [])],
           "affected_packages": report.get("affected_packages", [])}}
except Exception as e:
    out = {{"ok": False, "seconds": round(time.perf_counter() - t0, 1),
           "error": f"{{type(e).__name__}}: {{e}}"}}
print("###RESULT###" + json.dumps(out))
"""


def frozen_inventory() -> list[str]:
    if FROZEN_INV.exists():
        return json.loads(FROZEN_INV.read_text())
    return sorted(subprocess.run(["apt-mark", "showmanual"], capture_output=True,
                                 text=True, timeout=30).stdout.split())


def ssh_scenarios() -> dict:
    """hosts.json'dan SSH senaryo tanımları (erişim kontrolü main'de, seçim sonrası
    — bellek disiplini: senaryolar tek VM açıkken parça parça koşulabilmeli)."""
    hosts = json.loads((BASE / "config" / "hosts.json").read_text())["hosts"]
    scen = {}
    for entry in hosts:
        m = re.search(r"\d\d\.\d\d", entry["label"])
        if not m or m.group(0) not in SSH_TARGETS:
            continue
        cur = m.group(0)
        scen[f"ssh_{cur.replace('.', '')}_{SSH_TARGETS[cur].replace('.', '')}"] = {
            "current": cur, "target": SSH_TARGETS[cur],
            "packages": None, "host": entry["host"]}
    return scen


def run_one(sc: dict, env_over: dict, timeout: int) -> dict:
    # RAM bekçisi (3. donma olayının dersi — ab_llm.py ile aynı): S5'te risk
    # daha da yüksek (4 lab VM + LLM + embedding aynı anda).
    from tests.ab_llm import wait_for_ram
    if not wait_for_ram(3.0):
        return {"ok": False, "seconds": 0, "error": "ram-guard-abort"}
    packages = sc.get("packages")
    if packages == "REAL":
        packages = frozen_inventory()
    code = WORKER.format(base=str(BASE), target=sc["target"],
                         current=sc["current"], packages=packages,
                         host=sc.get("host"))
    env = {**os.environ, **env_over}
    t0 = time.perf_counter()
    try:
        proc = subprocess.run([sys.executable, "-c", code], env=env,
                              capture_output=True, text=True,
                              timeout=timeout, cwd=str(BASE))
        m = re.search(r"###RESULT###(.+)", proc.stdout)
        return json.loads(m.group(1)) if m else {
            "ok": False, "seconds": round(time.perf_counter() - t0, 1),
            "error": f"no-result (rc={proc.returncode}): {proc.stderr[-200:]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "seconds": timeout, "error": "timeout"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-ssh", action="store_true")
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--configs", default="eski,yeni")
    ap.add_argument("--scenarios", default=None,
                    help="virgüllü alt küme (ör. ssh_1804_2004) — bellek "
                         "disiplini: SSH bacakları tek VM açıkken koşulabilir")
    args = ap.parse_args()

    scenarios = dict(M8_SCENARIOS)
    if not args.skip_ssh:
        scenarios.update(ssh_scenarios())
    if args.scenarios:
        wanted = set(args.scenarios.split(","))
        unknown = wanted - set(scenarios)
        if unknown:
            raise SystemExit(f"bilinmeyen senaryo: {sorted(unknown)} — "
                             f"mevcut: {sorted(scenarios)}")
        scenarios = {k: v for k, v in scenarios.items() if k in wanted}

    # Erişim ön-kontrolü yalnız SEÇİLEN SSH senaryoları için
    from src.remote.ssh_runner import is_reachable
    for sname, sc in scenarios.items():
        if sc.get("host") and not is_reachable(sc["host"]):
            raise SystemExit(f"lab VM erişilemez: {sname} ({sc['host']}) — "
                             f"önce `virsh start` ile aç")

    results = []
    for cname in args.configs.split(","):
        env_over = CONFIGS[cname]
        for sname, sc in scenarios.items():
            rec = run_one(sc, env_over, args.timeout)
            rec.update({"config": cname, "scenario": sname})
            results.append(rec)
            status = (f"taslak={rec.get('draft')} v={rec.get('verified')} "
                      f"r={rec.get('rejected')} f={rec.get('flags')}"
                      if rec["ok"] else f"HATA: {rec['error'][:70]}")
            print(f"  [{cname}] {sname}: {rec['seconds']}s {status}", flush=True)

    OUT_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M")
    payload = {
        "sprint": "S5 update_plan_3 — kabul matrisi",
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
        "configs": CONFIGS,
        "llm": os.getenv("LLM_MODEL", "qwen2.5:7b (varsayılan)"),
        "results": results,
    }
    out = OUT_DIR / f"matrix_{stamp}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"[✓] sonuç: {out}")

    # Yan yana özet tablo (markdown) — rapora kopyalanabilir
    lines = ["| Senaryo | Konfig | Taslak | Doğrulanan | RED | FLAG | Süre |",
             "|---|---|---|---|---|---|---|"]
    for r in results:
        if r["ok"]:
            lines.append(f"| {r['scenario']} | {r['config']} | {r['draft']} | "
                         f"{r['verified']} | {r['rejected']} | {r['flags']} | "
                         f"{r['seconds']}s |")
        else:
            lines.append(f"| {r['scenario']} | {r['config']} | — | — | — | — | "
                         f"HATA: {r['error'][:40]} |")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
