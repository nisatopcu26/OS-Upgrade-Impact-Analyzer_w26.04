"""Doğruluk denetimi (accuracy audit) — rapor iddialarını kaynaklarıyla denetler.

Her iddia için: (1) atıf yapılan chunk Chroma'da bulunur, (2) sözcüksel varlık
kontrolü yeniden koşulur, (3) destek skoru sınıflanır, (4) iddia + kaynak metni
yan yana dökülür (elle inceleme için).

Kullanım:
  .venv/bin/python tests/accuracy_audit.py rapor1.json [rapor2.json ...] > audit.md
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.grounding import missing_hard_entities
from src.rag.vector_store import get_collection


def audit_report(path: str) -> list[dict]:
    r = json.loads(Path(path).read_text(encoding="utf-8"))
    col = get_collection()
    allowed = {r["current_version"], r["target_version"]}
    rows = []
    for c in r["claims"]:
        cid = c["chunk_ids"][0]
        got = col.get(ids=c["chunk_ids"], include=["documents"])
        source = " ".join(got["documents"]) if got["documents"] else ""
        # v2.1: eşleşme semantiği grounding'le ORTAK (kopya mantık yok)
        missing = missing_hard_entities(c["text"], source, allowed)
        # Raporda zaten FLAG'lenmiş (şeffafça işaretlenmiş) detaylar "sorunlu"
        # sayılmaz — kademeli politika denetimde de aynı anlama gelmeli
        flagged_terms = {f["term"] for f in c.get("flags", [])}
        missing = [m for m in missing if m not in flagged_terms]
        rows.append({
            "scenario": f"{r['current_version']}→{r['target_version']}",
            "claim": c["text"],
            "chunk_id": cid,
            "source_excerpt": (got["documents"][0][:160] if got["documents"] else "(YOK!)"),
            "score": c["support_score"],
            "missing_entities": missing,
            "flags": sorted(flagged_terms),
            "verdict": "SORUNLU" if (missing or not got["documents"]) else "sadık",
        })
    return rows


if __name__ == "__main__":
    from datetime import datetime

    all_rows = [row for p in sys.argv[1:] for row in audit_report(p)]
    bad = [r for r in all_rows if r["verdict"] != "sadık"]

    print(f"# Doğruluk Denetimi\n")
    print(f"*Üretim: {datetime.now().strftime('%Y-%m-%d %H:%M')} — "
          f"{len(sys.argv) - 1} rapor (M8 orijinal + grounding v2.1 regresyonu "
          f"+ uzak SSH senaryoları). FLAG'li detaylar raporda zaten işaretli "
          f"olduğundan 'sorunlu' sayılmaz.*\n")
    print(f"Toplam iddia: {len(all_rows)} | Sadık: {len(all_rows) - len(bad)} "
          f"| Sorunlu: {len(bad)}\n")
    for r in all_rows:
        flag = "⚠️ " if r["verdict"] != "sadık" else ""
        print(f"## {flag}[{r['scenario']}] skor={r['score']}")
        print(f"**İddia:** {r['claim']}")
        print(f"**Kaynak** `{r['chunk_id']}`: {r['source_excerpt']}...")
        if r["missing_entities"]:
            print(f"**Kaynakta bulunamayan varlıklar:** {r['missing_entities']}")
        if r["flags"]:
            print(f"**⚠️ Raporda işaretli detaylar (FLAG):** {r['flags']}")
        print()
