"""Zincir upgrade — Aşama 2 / Sprint 4: bacak-bacak analiz orkestrasyonu.

Her bacak, mevcut analiz zincirinden (agent.analyze — LLM sadece orada, tek
node'da) AYRI geçirilir; bacağın envanteri inventory_evolution'ın kaynağa
dayalı modeliyle gelir. Bu modülün kendisi deterministiktir: LLM çağrısı
analyze_fn'in içindedir.

Kısmi-hata politikası (D6): ilk bacak patlarsa hata AYNEN yükselir (routes
/analyze ile aynı eşlemeyi yapar: ConnectionError→502, ValueError→422,
RuntimeError→500). Sonraki bir bacak patlarsa tamamlanan bacaklar DÖNER +
`error` alanı doldurulur — tamamlanmış bacaklar bağımsız geçerli, kaynaklı
raporlardır; onları gizlemek de çöpe atmak da dürüst olmazdı.
"""

import time

from src.upgrade_path.inventory_evolution import evolve_inventory
from src.upgrade_path.path import compute_path

EVOLUTION_DISCLAIMER = (
    "Envanter evrimi bir MODELDİR: yalnızca release notes'ta AÇIKÇA "
    "'removed / no longer available' denen paketler bacaklar arasında "
    "düşürülür; notlarda yazmayan değişiklikler ve yeniden adlandırmalar "
    "modellenmez. Kesin gerçek ancak makine gerçekten upgrade edilip envanter "
    "yeniden okunarak bilinir.")


def analyze_chain(current: str, target: str,
                  packages: list[str] | None = None,
                  host: str | None = None,
                  corpus_fn=None, analyze_fn=None) -> dict:
    """current→target resmi LTS yolunun her bacağını ayrı analiz eder.

    corpus_fn / analyze_fn: test enjeksiyonu (projenin sayaç-enjeksiyonu
    deseni) — None ise gerçek Chroma korpusu / gerçek agent.analyze kullanılır.
    Lazy import: testler LLM/Chroma yığınını hiç yüklemez.
    """
    if analyze_fn is None:
        from src.agent.graph import analyze as analyze_fn  # noqa: PLW0127

    path_info = compute_path(current, target)
    if path_info["error"]:
        raise ValueError(path_info["error"])   # routes → 422 (/analyze ile aynı)

    warnings: list[str] = []
    if packages is not None:
        base = list(packages)
    else:
        from src.detector.package_inventory import get_inventory
        inv = get_inventory(host=host)
        base = list(inv.get("packages") or [])
        if inv.get("error"):
            # çökme yok sözleşmesi: envanter yoksa boş envanterle devam,
            # ama durum RAPORDA görünür (sessiz düşüş yasak)
            warnings.append(f"Envanter okunamadı ({inv['error']}) — zincir "
                            "boş envanterle analiz edildi.")

    evo = evolve_inventory(base, path_info["legs"], corpus_fn=corpus_fn)

    legs_out: list[dict] = []
    error: dict | None = None
    for from_v, to_v in path_info["legs"]:
        leg_inv = evo["per_leg"][(from_v, to_v)]
        t0 = time.time()
        try:
            report = analyze_fn(target_version=to_v, current_version=from_v,
                                packages=leg_inv, host=host)
        except Exception as exc:
            if not legs_out:
                raise          # ilk bacak: gösterecek bir şey yok, dürüst hata
            error = {"leg": [from_v, to_v], "detail": str(exc)}
            break
        report["duration_s"] = round(time.time() - t0, 1)
        legs_out.append({
            "from_version": from_v,
            "to_version": to_v,
            "inventory_size": len(leg_inv),
            "inventory": leg_inv,              # şeffaflık: UI expander'da görünür
            "evolution": evo["evolution"][(from_v, to_v)],
            "report": report,
        })

    return {
        "host": host,
        "current_version": current,
        "target_version": target,
        "upgrade_path": path_info,
        "legs": legs_out,
        "evolution_disclaimer": EVOLUTION_DISCLAIMER,
        "warnings": warnings,
        "error": error,
    }
