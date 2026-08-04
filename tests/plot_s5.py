"""S5 (update_plan_3) — sonuç görselleştirmeleri.

Üç figür üretir (docs/s5-matrix/figs/):
  fig_s2_kalibrasyon.png : eşik kalibrasyon dağılımları (3 mod strip-plot)
  fig_s4_ab.png          : LLM A/B küçük-katlar (qwen vurgulu)
  fig_s5_matris.png      : 6 senaryo × 2 konfig yan yana (yeni vurgulu)

Tasarım: dataviz yöntemi — form önce, renk sona; emfaz formu (konu mavi,
bağlam gri); kategorik renkler sabit sırayla; çift eksen yok; ince işaretler,
doğrudan etiketler, çekingen ızgara. Palet: doğrulanmış varsayılan
(mavi #2a78d6 slot-1, turuncu #eb6834 slot-2; mürekkepler aşağıda).

Koşum (matplotlib bench venv'inde):
  ../rag_layer_bench/.venv/bin/python tests/plot_s5.py
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE = Path(__file__).resolve().parents[1]
DOCS = BASE / "docs"
FIGS = DOCS / "s5-matrix" / "figs"

# Palet (referans örneği, light yüzey; validator: 3'lü PASS, aqua kullanılmadı)
BLUE = "#2a78d6"      # slot 1 — konu (yeni konfig / qwen / alakalı)
ORANGE = "#eb6834"    # slot 2 — ikinci sınıf (saçma)
GRAY = "#c3c2b7"      # de-emfaz / bağlam serisi
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "font.family": "sans-serif", "text.color": INK,
    "axes.edgecolor": BASELINE, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": False, "font.size": 9,
})


def style_ax(ax, keep_x=True):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if not keep_x:
        ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(length=0)


def fig_s2():
    mini = json.loads((DOCS / "s5-matrix" / "threshold_calib_all-MiniLM-L6-v2.json").read_text())
    bge = json.loads((DOCS / "s5-matrix" / "threshold_calib_bge-small-en-v1.5.json").read_text())
    panels = [
        ("MiniLM · öneksiz (eski)", mini["modes"]["ÖNEKSİZ"], 0.30),
        ("bge-small · öneksiz", bge["modes"]["ÖNEKSİZ"], None),
        ("bge-small · ÖNEKLİ (seçilen)", bge["modes"]["ÖNEKLİ"], 0.60),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.4), sharey=True)
    rng = np.random.default_rng(42)
    for ax, (title, d, thr) in zip(axes, panels):
        groups = [("alakalı", d["alakali"], BLUE, 0),
                  ("karışık", d["karisik"], GRAY, 1),
                  ("saçma", d["sacma"], ORANGE, 2)]
        for name, vals, color, x in groups:
            xs = x + rng.uniform(-0.16, 0.16, len(vals))
            ax.scatter(xs, vals, s=22, color=color, alpha=0.75,
                       edgecolors=SURFACE, linewidths=0.8, zorder=3)
        if thr is not None:
            ax.axhline(thr, color=INK2, lw=1.2, ls=(0, (4, 3)), zorder=2)
            ax.annotate(f"eşik {thr:.2f}", xy=(-0.44, thr), fontsize=8,
                        color=INK2, va="bottom", ha="left")
        rel_min, non_max = min(d["alakali"]), max(d["sacma"])
        ok = non_max < rel_min
        ax.annotate(f"alakalı-min {rel_min:.3f}", xy=(0, rel_min),
                    xytext=(0.28, rel_min), va="center",
                    fontsize=7.5, color=INK2)
        ax.annotate(f"saçma-maks {non_max:.3f}", xy=(2, non_max),
                    xytext=(1.35, non_max + 0.045), fontsize=7.5, color=INK2)
        ax.set_title(title + ("" if ok else "  —  BOŞLUK YOK"),
                     fontsize=9.5, color=(INK if ok else ORANGE), pad=8)
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(["alakalı", "karışık\n(bağlam)", "saçma"], fontsize=8)
        ax.set_xlim(-0.5, 2.5)
        ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
        style_ax(ax)
    axes[0].set_ylabel("iddia ↔ chunk kosinüs benzerliği", fontsize=8.5)
    fig.suptitle("S2 — Eşik kalibrasyonu: alakalı/saçma skor boşluğu (60 sadık + 5 saçma iddia)",
                 fontsize=11, x=0.02, y=0.985, ha="left", color=INK)
    fig.text(0.02, 0.895, "bge öneksiz modda boşluk kapanıyor; önekli modda açılıyor → eşik 0.60 (boşluğun ortası)",
             fontsize=8.5, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    fig.savefig(FIGS / "fig_s2_kalibrasyon.png", dpi=200)
    plt.close(fig)


def fig_s4():
    q = json.loads((DOCS / "ab-llm" / "ab_qwen2.5_7b_20260729.json").read_text())
    l = json.loads((DOCS / "ab-llm" / "ab_llama3.1_8b_20260729.json").read_text())

    def valid_json_runs(d):
        return sum(1 for r in d["runs"] if r.get("ok") and (r.get("verified", 0) + r.get("rejected", 0)) > 0)

    panels = [
        ("Geçme oranı", q["grounding_pass_rate"], l["grounding_pass_rate"], "{:.3f}", None),
        ("Doğrulanan / dakika", q["verified_per_minute"], l["verified_per_minute"], "{:.2f}", None),
        ("Ortalama süre (s)", q["avg_seconds_per_run"], l["avg_seconds_per_run"], "{:.0f} s", "düşük iyi"),
        ("Geçerli JSON koşusu", valid_json_runs(q), valid_json_runs(l), "{:.0f}/9", None),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(9.6, 2.7))
    for ax, (title, qv, lv, fmt, note) in zip(axes, panels):
        ax.barh([1, 0], [qv, lv], height=0.36,
                color=[BLUE, GRAY], zorder=3)
        ax.set_ylim(-0.55, 1.55)
        for y, v in ((1, qv), (0, lv)):
            ax.annotate(fmt.format(v), xy=(v, y), xytext=(4, 0),
                        textcoords="offset points", va="center",
                        fontsize=9, color=INK)
        ax.set_yticks([1, 0])
        ax.set_yticklabels(["qwen2.5:7b", "llama3.1:8b"], fontsize=8.5)
        ax.set_title(title + (f"  ({note})" if note else ""), fontsize=9, pad=6, color=INK)
        ax.set_xlim(0, max(qv, lv) * 1.32)
        ax.set_xticks([])
        style_ax(ax, keep_x=False)
    fig.suptitle("S4 — LLM A/B (yeni konfig, 3 senaryo × 3 tekrar): fark kapandı, qwen 2.3× hızlı",
                 fontsize=11, x=0.02, ha="left", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(FIGS / "fig_s4_ab.png", dpi=200)
    plt.close(fig)


def fig_s5():
    results = []
    for p in sorted((DOCS / "s5-matrix").glob("matrix_*.json")):
        results += json.loads(p.read_text())["results"]
    order = ["m8_2204_2404_real", "m8_2004_2204_server", "m8_1804_2004_legacy",
             "ssh_2204_2404", "ssh_2004_2204", "ssh_1804_2004"]
    labels = {"m8_2204_2404_real": "M8 22.04→24.04 (gerçek)",
              "m8_2004_2204_server": "M8 20.04→22.04 (sunucu)",
              "m8_1804_2004_legacy": "M8 18.04→20.04 (legacy)",
              "ssh_2204_2404": "SSH 22.04→24.04",
              "ssh_2004_2204": "SSH 20.04→22.04",
              "ssh_1804_2004": "SSH 18.04→20.04 (469 pkt)"}
    by = {}
    for r in results:
        if r.get("ok"):
            by[(r["scenario"], r["config"])] = r
    scen = [s for s in order if (s, "eski") in by and (s, "yeni") in by]
    y = np.arange(len(scen))[::-1]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 3.6), sharey=True)
    h = 0.34
    for ax, metric, fmt, xmax_pad in (
            (ax1, "oran", "{:.2f}", 1.28), (ax2, "sure", "{:.0f} s", 1.30)):
        for dy, cfg, color in ((h / 2 + 0.02, "yeni", BLUE), (-h / 2 - 0.02, "eski", GRAY)):
            vals = []
            for s in scen:
                r = by[(s, cfg)]
                vals.append(r["verified"] / r["draft"] if metric == "oran" else r["seconds"])
            ax.barh(y + dy, vals, height=h, color=color, zorder=3)
            for yy, v, s in zip(y + dy, vals, scen):
                extra = ""
                if metric == "oran" and by[(s, cfg)]["rejected"]:
                    extra = f"  ({by[(s, cfg)]['rejected']} RED)"
                ax.annotate(fmt.format(v) + extra, xy=(v, yy), xytext=(4, 0),
                            textcoords="offset points", va="center",
                            fontsize=8, color=INK)
        ax.set_xticks([])
        style_ax(ax, keep_x=False)
    ax1.set_yticks(y)
    ax1.set_yticklabels([labels[s] for s in scen], fontsize=8.5)
    ax1.set_title("Doğrulanan / taslak oranı", fontsize=9.5, color=INK)
    ax2.set_title("Süre (düşük iyi)", fontsize=9.5, color=INK)
    ax1.set_xlim(0, 1.28)
    ax2.set_xlim(0, max(by[(s, c)]["seconds"] for s in scen for c in ("eski", "yeni")) * 1.30)
    handles = [plt.Rectangle((0, 0), 1, 1, color=BLUE),
               plt.Rectangle((0, 0), 1, 1, color=GRAY)]
    fig.legend(handles, ["yeni (bge-small + 0.60)", "eski (MiniLM + 0.30)"],
               loc="upper right", frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.99, 0.97))
    fig.suptitle("S5 — Kabul matrisi: 6 senaryo × 2 konfigürasyon (LLM sabit: qwen2.5:7b)",
                 fontsize=11, x=0.02, ha="left", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(FIGS / "fig_s5_matris.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    FIGS.mkdir(parents=True, exist_ok=True)
    fig_s2()
    fig_s4()
    fig_s5()
    print(f"[✓] figürler: {FIGS}")
