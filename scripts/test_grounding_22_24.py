"""Grounding + 2./3. kanit katmanlari, 22.04->24.04 senaryosu (varsayilan
model qwen2.5:7b -- MODEL_OVERRIDES bu cifti kapsamiyor). Ayni paket listesi,
26.04 testiyle karsilastirilabilir olsun diye."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.graph import analyze

FAKE_PACKAGES = [
    "php", "postgresql", "openssh-server", "samba", "mysql-server",
    "dovecot-core", "haproxy", "squid", "sssd", "systemd",
    "python3", "gcc", "chrony", "clamav", "django",
]

report = analyze(
    target_version="24.04",
    current_version="22.04",
    packages=FAKE_PACKAGES,
)

Path("data/eval").mkdir(exist_ok=True)
Path("data/eval/grounding_report_22_24.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2)
)

print("=== STATS ===")
print(json.dumps(report["stats"], indent=2))
print(f"\n=== MODEL: {report['model']} ===")

apt_cited = [c for c in report["claims"] if any("apt-relations_" in cid for cid in c["chunk_ids"])]
news_cited = [c for c in report["claims"] if any("news-debian_" in cid for cid in c["chunk_ids"])]

print(f"\n=== apt-relations atifi yapan iddialar ({len(apt_cited)}) ===")
for c in apt_cited:
    print(f"- {c['text']}")
    print(f"  chunk_ids: {c['chunk_ids']}")

print(f"\n=== news-debian atifi yapan iddialar ({len(news_cited)}) ===")
for c in news_cited:
    print(f"- {c['text']}")
    print(f"  chunk_ids: {c['chunk_ids']}")

print(f"\n=== TUM VERIFIED CLAIMS ({len(report['claims'])}) ===")
for c in report["claims"]:
    print(f"- {c['text'][:100]}")
    print(f"  chunk_ids: {c['chunk_ids']}")
