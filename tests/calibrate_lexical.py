"""Grounding v2.1 / S1 — sözcüksel kalibrasyon aracı.

Gerçek rapor iddiaları (docs/sample-reports/*.json) üzerinde, YENİ yumuşak
varlık sınıfının (düz küçük-harf terimler) kaç yanlış alarm üreteceğini ölçer:

  - temiz      : tüm yumuşak terimler atıf yapılan chunk'ta bulundu
  - FLAG-adayı : terim korpustA var ama atıf yapılan chunk'ta yok (yanlış atıf?)
  - RED-adayı  : terim ne atıfta ne korpusta (uydurma şüphesi)

Hedef (kabul kriteri): 20 sadık iddiada 0 RED-adayı, ~0 FLAG-adayı.
Bu iddialar accuracy-audit'te elle doğrulanmış SADIK iddialar olduğundan,
her alarm ya stopword eksiğidir (listeye eklenir) ya da gerçek bir sınır
vakasıdır (not edilir, S4 politikasına girdi olur).

Kullanım:
  .venv/bin/python tests/calibrate_lexical.py docs/sample-reports/*.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# v2.1 S3'ten itibaren: kalibrasyon GERÇEK motoru kullanır (kopya mantık yok)
from src.agent.grounding import (
    _entity_in_text, _extract_soft_entities,
    corpus_vocab_for, missing_hard_entities,
)
from src.rag.vector_store import get_collection

soft_candidates = _extract_soft_entities  # geriye dönük ad (S1 çıktılarıyla kıyas)


def corpus_vocab(col, version: str) -> set[str]:
    return corpus_vocab_for(version)


def calibrate(paths: list[str]) -> int:
    col = get_collection()
    total = clean = flag = red = 0

    for p in paths:
        r = json.loads(Path(p).read_text(encoding="utf-8"))
        target = r["target_version"]
        vocab = corpus_vocab(col, target)
        allowed = {r["current_version"].lower(), target.lower()}
        print(f"\n=== {Path(p).name} ({r['current_version']}→{target}) "
              f"— korpus sözlüğü: {len(vocab)} terim ===")

        for c in r["claims"]:
            total += 1
            got = col.get(ids=c["chunk_ids"], include=["documents", "metadatas"])
            source = (" ".join(got["documents"]) + " "
                      + " ".join(m.get("section_title", "")
                                 for m in got["metadatas"])).lower()

            hard = missing_hard_entities(c["text"], source, allowed)
            cands = soft_candidates(c["text"]) - allowed
            missing = sorted(t for t in cands
                             if not _entity_in_text(t, source))
            nowhere = sorted(t for t in missing if t not in vocab)
            in_corpus = sorted(t for t in missing if t in vocab)

            if nowhere:
                red += 1
                status = "RED-adayı "
            elif in_corpus:
                flag += 1
                status = "FLAG-adayı"
            else:
                clean += 1
                status = "temiz     "
            print(f"[{status}] {c['text'][:78]}")
            if hard:
                print(f"             SERT-EKSİK (regresyon!): {hard}")
            if in_corpus:
                print(f"             korpusta-var-atıfta-yok: {in_corpus}")
            if nowhere:
                print(f"             HİÇBİR-YERDE-YOK: {nowhere}")

    print(f"\nÖZET: {total} iddia | temiz {clean} | FLAG-adayı {flag} | RED-adayı {red}")
    return red


if __name__ == "__main__":
    paths = sys.argv[1:] or sorted(
        str(p) for p in Path("docs/sample-reports").glob("*.json"))
    sys.exit(1 if calibrate(paths) else 0)
