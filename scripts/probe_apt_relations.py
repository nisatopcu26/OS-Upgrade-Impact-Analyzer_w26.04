"""Apt Breaks/Conflicts/Replaces/Provides -- izole kesif, src/'e dokunmadan.
Amac: golden-set'teki sahte envanterin ne kadari gercek iliski verisi tasiyor?
"""
import subprocess
import re
import sys

HOST = "nisa@192.168.64.2"

PACKAGES = [
    "php8.5", "postgresql-18", "openssh-server", "samba", "mysql-server",
    "dovecot-core", "haproxy", "squid", "sssd", "systemd",
    "python3", "gcc", "chrony", "clamav", "django",
]

FIELDS = ("Breaks", "Conflicts", "Replaces", "Provides")

def get_relations(pkg: str) -> dict:
    cmd = f"apt-cache show {pkg} 2>/dev/null | head -30"
    result = subprocess.run(["ssh", HOST, cmd], capture_output=True, text=True, timeout=15)
    out = {}
    for line in result.stdout.splitlines():
        for field in FIELDS:
            if line.startswith(f"{field}:"):
                out[field] = line[len(field)+1:].strip()
                break
        if line.startswith("Package:"):
            continue
    return out

print(f"{'paket':20} {'alan_sayisi':12} detay")
print("-" * 90)
has_data, empty = 0, 0
for pkg in PACKAGES:
    rel = get_relations(pkg)
    if rel:
        has_data += 1
        detail = " | ".join(f"{k}={v[:40]}" for k, v in rel.items())
    else:
        empty += 1
        detail = "(bos)"
    print(f"{pkg:20} {len(rel):12} {detail}")

print()
print(f"Veri tasiyan: {has_data}/{len(PACKAGES)}  ({100*has_data/len(PACKAGES):.0f}%)")
