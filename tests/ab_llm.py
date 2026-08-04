"""S4 (update_plan_3) — LLM A/B koşu aracı: qwen2.5:7b (kilitli) vs llama3.1:8b.

rag_layer_bench/bench_llm.py düzeneğinin canlı-sistem uyarlaması. Farklar:
- Sonuçlar docs/ab-llm/ altına YENİ dosyalara yazılır — tarihsel
  rag_layer_bench sonuçlarının üzerine yazılmaz (raporlama standardı).
- Koşular GÜNCEL varsayılan konfigde (S2 sonrası: bge-small + eşik 0.60 +
  S3 sözcükseli). A/B içsel geçerli (iki modelde tek değişken LLM); mutlak
  sayılar araştırma koşularıyla (MiniLM+0.30+S3-öncesi) bire bir
  kıyaslanamaz — konfig damgası çıktıda.
- Raporun yeni 'model' alanı (S4) her koşuda doğrulanır: env ile istenen
  model, raporun beyan ettiği modelle aynı olmalı.

RAM bekçisi (2026-07-29 3. donma olayının dersi): her koşudan önce
MemAvailable kontrol edilir — eşiğin altındaysa bekler, düzelmezse koşuyu
İPTAL eder (çökmektense eksik ölçüm). Ollama'nın RAM'e taşan 7B modeli
(+KV cache) + worker'ın embedding yükü üst üste ~6 GB ister; masaüstü
uygulamalarıyla birlikte 15 GB sınırı aşılabiliyor. Koşu sırasında tarayıcı
gibi ağır uygulamalar kapalı tutulmalı.

Kullanım:
  .venv/bin/python tests/ab_llm.py --model qwen2.5:7b   [--repeats 3]
  .venv/bin/python tests/ab_llm.py --model llama3.1:8b  [--repeats 3]
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
OUT_DIR = BASE / "docs" / "ab-llm"
FROZEN_INV = BASE.parent / "rag_layer_bench" / "data" / "inventory_real.json"

# M8 senaryolarının birebir karşılığı (bench_llm.py ile aynı listeler —
# araştırma koşularıyla senaryo-düzeyi kıyaslanabilirlik)
SCENARIOS = {
    "s1_2204_2404_real": {"current": "22.04", "target": "24.04", "packages": "REAL"},
    "s2_2004_2204_server": {"current": "20.04", "target": "22.04",
                            "packages": ["php", "php-fpm", "postgresql", "mysql-server",
                                         "docker.io", "nginx", "redis-server", "haproxy",
                                         "openssh-server", "certbot"]},
    "s3_1804_2004_legacy": {"current": "18.04", "target": "20.04",
                            "packages": ["python2", "php", "chrony", "corosync",
                                         "samba", "ntp", "apache2", "mysql-server"]},
}

WORKER = r"""
import json, sys, time
sys.path.insert(0, {base!r})
from src.agent.graph import analyze
t0 = time.perf_counter()
try:
    report = analyze({target!r}, current_version={current!r}, packages={packages!r})
    out = {{"ok": True, "seconds": round(time.perf_counter() - t0, 1),
           "model_field": report.get("model"),
           "verified": len(report.get("claims", [])),
           "rejected": len(report.get("rejected_claims", [])),
           "reject_reasons": [c.get("reject_reason") for c in report.get("rejected_claims", [])],
           "flags": sum(len(c.get("flags") or []) for c in report.get("claims", [])),
           "support_scores": [c.get("support_score") for c in report.get("claims", [])]}}
except Exception as e:
    out = {{"ok": False, "seconds": round(time.perf_counter() - t0, 1),
           "error": f"{{type(e).__name__}}: {{e}}"}}
print("###RESULT###" + json.dumps(out))
"""


def mem_available_gb() -> float:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024 / 1024
    return 0.0


def wait_for_ram(min_gb: float, max_wait_s: int = 1800) -> bool:
    """RAM bekçisi: eşik sağlanana dek bekler; süre dolarsa False (İPTAL).

    3. donma olayının (2026-07-29) mekanik karşılığı — 'tek ağır süreç'
    kuralı artık araçta zorlanıyor, insan disiplinine emanet değil.

    Eşik OOM-koruma çizgisidir (varsayılan 3 GB), "rahat çalışma" çizgisi
    değil: Ollama keep-alive modeli koşular arasında bellekte tuttuğundan
    2. koşudan itibaren MemAvailable doğal olarak düşük seyreder — yüksek
    bir eşik her koşuda haksız bekletir. Çökme riski available ~0 +
    swap-thrash bölgesinde; 3 GB + boş swap tamponu güvenli sınır.
    """
    t0 = time.time()
    while time.time() - t0 < max_wait_s:
        avail = mem_available_gb()
        if avail >= min_gb:
            return True
        print(f"  [RAM bekçisi] {avail:.1f} GB müsait < eşik {min_gb} GB — "
              f"30s bekleniyor (ağır uygulamaları kapatın)...", flush=True)
        time.sleep(30)
    return False


def frozen_inventory() -> list[str]:
    """Araştırma koşularının dondurduğu envanter — aynısı kullanılır."""
    if FROZEN_INV.exists():
        return json.loads(FROZEN_INV.read_text())
    pkgs = subprocess.run(["apt-mark", "showmanual"], capture_output=True,
                          text=True, timeout=30).stdout.split()
    return sorted(pkgs)


def ollama_stop_all():
    ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout
    for line in ps.splitlines()[1:]:
        parts = line.split()
        if parts:
            subprocess.run(["ollama", "stop", parts[0]], capture_output=True)


def model_digest(model: str) -> str:
    out = subprocess.run(["ollama", "list"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split()
        # TAM eşleşme — startswith 'qwen2.5:7b' isterken 'qwen2.5:7b-instruct-q8_0'
        # satırını yakalıyordu (2026-07-29 damga hatası dersi)
        if parts and parts[0] == model:
            return parts[1]
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument("--min-ram-gb", type=float, default=3.0,
                    help="koşu öncesi gereken MemAvailable (OOM koruma çizgisi)")
    args = ap.parse_args()

    from config.settings import EMBEDDING_MODEL, SIMILARITY_THRESHOLD

    inv = frozen_inventory()
    ollama_stop_all()

    runs = []
    for sname, sc in SCENARIOS.items():
        packages = inv if sc["packages"] == "REAL" else sc["packages"]
        for rep in range(args.repeats):
            if not wait_for_ram(args.min_ram_gb):
                print(f"[!] RAM eşiği ({args.min_ram_gb} GB) 5 dk içinde "
                      f"sağlanamadı — koşu İPTAL (çökmektense eksik ölçüm). "
                      f"Kaydedilen: {len(runs)} koşu.", flush=True)
                runs.append({"ok": False, "seconds": 0, "scenario": sname,
                             "repeat": rep, "error": "ram-guard-abort"})
                break
            avail_before = round(mem_available_gb(), 1)
            code = WORKER.format(base=str(BASE), target=sc["target"],
                                 current=sc["current"], packages=packages)
            env = {**os.environ, "LLM_MODEL": args.model}
            t0 = time.perf_counter()
            try:
                proc = subprocess.run([sys.executable, "-c", code], env=env,
                                      capture_output=True, text=True,
                                      timeout=args.timeout, cwd=str(BASE))
                m = re.search(r"###RESULT###(.+)", proc.stdout)
                rec = json.loads(m.group(1)) if m else {
                    "ok": False, "seconds": round(time.perf_counter() - t0, 1),
                    "error": f"no-result (rc={proc.returncode}): {proc.stderr[-200:]}"}
            except subprocess.TimeoutExpired:
                rec = {"ok": False, "seconds": args.timeout, "error": "timeout"}
            rec.update({"scenario": sname, "repeat": rep,
                        "mem_available_gb_before": avail_before})
            time.sleep(10)   # koşular arası bellek oturması (3. donma dersi)
            if rec.get("ok") and rec.get("model_field") != args.model:
                rec["warning"] = (f"model alanı uyuşmuyor: rapor "
                                  f"{rec.get('model_field')!r} beyan etti")
            runs.append(rec)
            status = (f"v={rec.get('verified')} r={rec.get('rejected')} "
                      f"f={rec.get('flags')}" if rec["ok"]
                      else f"HATA: {rec['error'][:60]}")
            print(f"  {sname} #{rep}: {rec['seconds']}s {status}", flush=True)

    ok = [r for r in runs if r["ok"]]
    total_v = sum(r["verified"] for r in ok)
    total_draft = sum(r["verified"] + r["rejected"] for r in ok)
    total_min = sum(r["seconds"] for r in ok) / 60 if ok else 0
    hist = {}
    for r in ok:
        for reason in r.get("reject_reasons", []):
            hist[reason] = hist.get(reason, 0) + 1

    summary = {
        "sprint": "S4 update_plan_3 (canlı sistem A/B)",
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
        "model": args.model, "digest": model_digest(args.model),
        "config": {"embedding_model": EMBEDDING_MODEL,
                   "similarity_threshold": SIMILARITY_THRESHOLD,
                   "lexical": "S3 sonrası (-ing toleransı dahil)",
                   "hardware": "RTX 3050 Laptop 4GB VRAM / 15GB RAM"},
        "repeats": args.repeats, "runs_ok": len(ok), "runs_fail": len(runs) - len(ok),
        "total_draft_claims": total_draft, "total_verified": total_v,
        "grounding_pass_rate": round(total_v / total_draft, 3) if total_draft else None,
        "verified_per_minute": round(total_v / total_min, 2) if total_min else None,
        "avg_seconds_per_run": round(sum(r["seconds"] for r in ok) / len(ok), 1) if ok else None,
        "reject_reason_hist": hist,
        "runs": runs,
    }

    OUT_DIR.mkdir(exist_ok=True)
    safe = args.model.replace(":", "_").replace("/", "_")
    out = OUT_DIR / f"ab_{safe}_{time.strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"[✓] sonuç: {out}")
    ollama_stop_all()


if __name__ == "__main__":
    main()
