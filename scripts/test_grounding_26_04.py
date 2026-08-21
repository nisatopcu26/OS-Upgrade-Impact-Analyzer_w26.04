"""Grounding katmani 26.04 uzerinde: analyze() ucdan uca, sahte envanterle (M8 yontemi)."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.graph import analyze

# Golden set'teki paketlerle ortuşen, gercekci bir envanter
FAKE_PACKAGES = [
    "php", "postgresql", "openssh-server", "samba", "mysql-server",
    "dovecot-core", "haproxy", "squid", "sssd", "systemd",
    "python3", "gcc", "chrony", "clamav", "django",
]

report = analyze(
    target_version="26.04",
    current_version="24.04",
    packages=FAKE_PACKAGES,
)

Path("data/eval").mkdir(exist_ok=True)
Path("data/eval/grounding_report_26_04.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2)
)

print("=== STATS ===")
print(json.dumps(report["stats"], indent=2))

print(f"\n=== MODEL: {report['model']} ===")

print(f"\n=== VERIFIED CLAIMS ({len(report['claims'])}) ===")
for c in report["claims"]:
    flag_str = f"  [FLAGS: {c['flags']}]" if c.get("flags") else ""
    print(f"\n- {c['text']}")
    print(f"  chunk_ids: {c['chunk_ids']}  support={c['support_score']}{flag_str}")

print(f"\n=== REJECTED CLAIMS ({len(report['rejected_claims'])}) ===")
for c in report["rejected_claims"]:
    print(f"\n- [{c['reject_reason']}] {c['text'][:150]}")
    if c.get("missing_entities"):
        print(f"  missing: {c['missing_entities']}")
    if c.get("support_score") is not None:
        print(f"  support_score: {c['support_score']}")

print(f"\n=== AFFECTED PACKAGES (kullanicinin envanteriyle kesisen) ===")
print(report["affected_packages"])
