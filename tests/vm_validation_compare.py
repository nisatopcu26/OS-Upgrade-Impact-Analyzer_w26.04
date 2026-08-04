"""Zincir Sprint 6 — envanter evrimi modelini GERÇEK VM upgrade'iyle kıyaslar.

Kullanım (klon VM upgrade edildikten sonra; bacak sürümleri opsiyonel,
varsayılan 18.04→20.04):
  .venv/bin/python tests/vm_validation_compare.py \
      docs/vm-validation/manual-1804-before.txt \
      docs/vm-validation/manual-2004-after.txt [18.04 20.04]

Metrik (dürüst tanım — architecture.md "Bilinen sınırlar" ile birlikte oku):
- predicted_removed : modelin 18.04→20.04 bacağı için kanıtlı kaldırma tahmini
- actually_gone     : before − after (apt-mark showmanual anlık görüntü farkı)
- precision         : tahminlerin ne kadarı gerçekten kayboldu
- recall            : kaybolanların ne kadarı tahmin edildi — DÜŞÜK BEKLENİR:
  (a) release notes her kaldırmayı yazmaz (modelin belgeli sınırı),
  (b) do-release-upgrade manuel/otomatik işaretlerini de değiştirir — her
      "kaybolan" gerçek kaldırma değildir. Anlaşmazlıkta klonda
      `dpkg -l <paket>` çapraz kontrolü yapılır.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.upgrade_path.inventory_evolution import evolve_inventory  # noqa: E402

def main(before_path: str, after_path: str,
         from_v: str = "18.04", to_v: str = "20.04") -> None:
    leg = (from_v, to_v)
    before = set(Path(before_path).read_text(encoding="utf-8").split())
    after = set(Path(after_path).read_text(encoding="utf-8").split())
    print(f"Bacak: {from_v} → {to_v}")
    print(f"Envanter: önce {len(before)} / sonra {len(after)} paket")

    evo = evolve_inventory(sorted(before), [leg])
    evidence = evo["evolution"][leg]["removed"]
    predicted = {r["package"] for r in evidence}
    actually_gone = before - after

    tp = sorted(predicted & actually_gone)
    fp = sorted(predicted - actually_gone)   # tahmin edildi ama duruyor
    fn = sorted(actually_gone - predicted)   # kayboldu ama tahmin edilmedi

    print(f"\nModel tahmini (kanıtlı): {sorted(predicted) or '—'}")
    for r in evidence:
        print(f"  {r['package']} [{r['chunk_id']}]: {r['quote'][:90]}")
    print(f"\nGerçekte kaybolan ({len(actually_gone)}): "
          f"{sorted(actually_gone)[:20]}{' ...' if len(actually_gone) > 20 else ''}")

    print(f"\nİsabet (TP): {tp or '—'}")
    print(f"Yanlış alarm (FP — tahmin edildi ama klonda duruyor, dpkg -l ile "
          f"çapraz kontrol et): {fp or '—'}")
    print(f"Kaçan (FN — beklenen: release notes yazmadıysa model göremez): "
          f"{len(fn)} paket")

    if predicted:
        print(f"\nprecision = {len(tp)}/{len(predicted)} "
              f"= {len(tp) / len(predicted):.2f}")
    else:
        print("\nprecision = tanımsız (model hiç tahmin üretmedi)")
    if actually_gone:
        print(f"recall    = {len(tp)}/{len(actually_gone)} "
              f"= {len(tp) / len(actually_gone):.2f}  (düşük olması belgeli sınır)")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 5):
        sys.exit(__doc__)
    main(*sys.argv[1:])
