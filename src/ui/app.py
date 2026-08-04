"""M7 — Streamlit arayüzü.

Çalıştır (API açıkken):
  .venv/bin/uvicorn src.api.main:app --port 8010          # terminal 1
  .venv/bin/streamlit run src/ui/app.py                    # terminal 2
(Not: port 8000 bu makinede başka projede — 8010 kullanılıyor.)

UI Türkçe; rapor içeriği İngilizce (kilitli karar), kaynak atıfları her iddiada.
"""

import json
import sys
from pathlib import Path

# streamlit run, script'in klasörünü (src/ui) sys.path'e koyar — proje kökünü
# değil. config/src import'ları için kökü ekle (nereden çalıştırılırsa çalışsın).
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

import requests
import streamlit as st

from config.settings import API_BASE_URL
from src.upgrade_path.path import compute_path   # hafif modül (ağır import yok)

st.set_page_config(page_title="OS Upgrade Impact Analyzer", page_icon="🐧",
                   layout="wide")
st.title("🐧 OS Upgrade Impact Analyzer")
st.caption("Resmi kaynaklara dayalı, makineye özel Ubuntu upgrade analizi — "
           "kaynaksız iddia üretmez. Uzak sunucular SSH ile, agentless analiz edilir.")

CATEGORY_LABELS = {
    "package": "📦 Paketlerini etkileyen değişiklikler",
    "known_issue": "⚠️ Bilinen sorunlar",
    "general": "🔄 Genel değişiklikler",
}


def render_report(report: dict) -> None:
    """Tek analiz raporunun gövdesi — tek-mod VE zincir sekmeleri paylaşır.

    (Zincir Sprint 5 refactor'ı: eski inline gövdenin SAF taşınmış hali,
    davranış değişikliği yok. Başlık/kapsam kartı çağıranda kalır.)
    """
    s = report["stats"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Doğrulanmış iddia", s["verified"])
    m2.metric("Reddedilen (kaynaksız)", s["rejected"])
    m3.metric("Etkilenen paketin", len(report["affected_packages"]))
    m4.metric("Süre", f"{report.get('duration_s', '—')}s")

    if report["affected_packages"]:
        st.warning("**Senin makinende etkilenen paketler:** "
                   + ", ".join(f"`{p}`" for p in report["affected_packages"]))

    st.info(report["summary"])

    for category, label in CATEGORY_LABELS.items():
        claims = [c for c in report["claims"] if c["category"] == category]
        if not claims:
            continue
        st.markdown(f"### {label}")
        for c in claims:
            pkg = f" — `{c['affected_package']}`" if c.get("affected_package") else ""
            flags = c.get("flags") or []
            # v2.1: flag'li iddia doğrulanmıştır ama BİR detayı atıf yapılan
            # kaynakta bulunamamıştır — iddiayı gömmeden görünür işaretle
            flag_mark = " ⚠️" if flags else ""
            st.markdown(f"- {c['text']}{pkg}{flag_mark}")
            # Destek skoru görsel işareti: yüksek/orta/düşük aynı görünmesin
            score = c["support_score"]
            icon = "🟢" if score >= 0.7 else ("🟡" if score >= 0.45 else "🟠")
            with st.expander(f"{icon} kaynaklar ({len(c['sources'])}) · "
                             f"destek skoru {score}"
                             + (f" · ⚠️ {len(flags)} işaretli detay" if flags else "")):
                for src in c["sources"]:
                    st.markdown(f"[{src['chunk_id']}]({src['url']}) — "
                                f"çekilme: {src['scraped_at'][:19]}")
                for f in flags:
                    st.markdown(f"⚠️ atıf yapılan kaynakta doğrulanamayan detay: "
                                f"`{f['term']}` ({f['reason']})")

    if report["not_found_notes"]:
        st.markdown("### 🚫 Kaynak bulunamadı (uydurma önlendi)")
        for note in report["not_found_notes"]:
            st.markdown(f"- {note}")

    with st.expander("Veri tazeliği ve uyarılar"):
        st.json({"freshness": report["freshness"],
                 "warnings": report["warnings"],
                 "package_candidates": report["package_candidates"]})


@st.cache_data(ttl=60)
def api_get(path: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE_URL}{path}", timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None


def _lab_hosts() -> dict[str, str]:
    """config/hosts.json → {etiket: kullanici@ip} (dosya yoksa boş)."""
    try:
        cfg = json.loads((_ROOT / "config" / "hosts.json").read_text(encoding="utf-8"))
        return {h["label"]: h["host"] for h in cfg.get("hosts", [])}
    except (OSError, ValueError):
        return {}


# --- Hedef seçimi (v2): lokal / lab VM'leri / özel host ---
LOCAL_LABEL = "💻 Bu makine (lokal)"
lab = _lab_hosts()
choice = st.selectbox("🎯 Analiz hedefi", [LOCAL_LABEL, *lab, "✏️ Özel host..."],
                      help="Uzak sunucular SSH ile okunur (agentless: hedefe "
                           "hiçbir şey kurulmaz).")
if choice == "✏️ Özel host...":
    host = st.text_input("Hedef (kullanici@ip)",
                         placeholder="ubuntu@192.168.1.10").strip() or None
else:
    host = lab.get(choice)          # LOCAL_LABEL → None (lokal analiz)

_qs = f"?host={host}" if host else ""
detect = api_get(f"/detect{_qs}")
versions = api_get("/versions")
packages = api_get(f"/packages{_qs}")

if detect is None:
    st.error(f"API'ye ulaşılamıyor ({API_BASE_URL}). Önce şunu çalıştır:\n\n"
             "`.venv/bin/uvicorn src.api.main:app --port 8010`")
    st.stop()

# Uzak hedef erişilebilirlik göstergesi — kırmızıysa analiz butonu açılmaz
reachable = bool(detect.get("version"))
if host:
    if reachable:
        st.success(f"🟢 Bağlandı: `{host}` — Ubuntu {detect['version']} "
                   f"({detect.get('codename') or '?'})")
    else:
        st.error(f"🔴 Hedef sunucuya erişilemedi: `{host}` — "
                 f"{detect.get('error') or 'bağlantı hatası'}")

# --- Sol panel: sistem bilgisi ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Mevcut sürüm",
              f"Ubuntu {detect['version']}" if detect.get("version") else "Tespit edilemedi",
              detect.get("codename") or "")
with col2:
    st.metric("Kurulu paket (elle)",
              packages["count"] if packages else "—",
              "apt-mark showmanual" + (" · SSH" if host else ""))

current = detect.get("version")
supported = versions["supported"] if versions else []
# v2 düzeltmesi: mevcut sürümden BÜYÜK hedef yoksa downgrade önerme —
# eski `or supported` fallback'i 24.04 makinesinde 18.04'ü hedef gösteriyordu
targets = [v for v in supported if current and v > current]
target = None
with col3:
    if targets:
        target = st.selectbox("Hedef sürüm", targets, index=len(targets) - 1)

if current and reachable and not targets:
    st.success(f"✅ Ubuntu {current} zaten desteklenen en güncel LTS — "
               "upgrade hedefi yok, analiz gerekmiyor.")

# Zincir Aşama 1 — seçim ANINDA dürüst yol bilgisi: hedef bir sonraki LTS
# değilse kullanıcı daha analiz başlamadan yolu görür. Tek bacakta görünmez.
path_info = compute_path(current, target) if (current and target) else None
multi_leg = bool(path_info and path_info["path"] and not path_info["is_direct"])
chain_mode = False
if multi_leg:
    st.warning(
        f"⚠️ **Resmi upgrade yolu: {' → '.join(path_info['path'])}** — "
        f"Ubuntu doğrudan atlamayı desteklemez (`do-release-upgrade` sıralı "
        f"gider). Varsayılan analiz yalnızca **{target}** değişikliklerini "
        f"kapsar; ara sürümler ({', '.join(path_info['skipped_intermediates'])}) "
        "dahil değildir.")
    chain_mode = st.checkbox(
        f"🔗 Zinciri analiz et ({len(path_info['legs'])} bacak — her bacak "
        "kendi envanteriyle ayrı analiz edilir)",
        value=False,
        help="Her bacak ayrı LLM analizi demektir: toplam "
             f"~{2 * len(path_info['legs'])} dakikaya kadar sürebilir. "
             "Bacaklar arasında envanter, release notes'ta açıkça kaldırıldığı "
             "yazan paketler düşürülerek taşınır (kaynak kanıtlı).")

st.divider()

can_analyze = reachable and target is not None
if can_analyze and st.button("🔍 Upgrade etkisini analiz et", type="primary",
                             use_container_width=True):
    if chain_mode:
        endpoint, timeout = "/analyze-chain", 1800   # 3 bacak ≈ 5-6 dk
        spinner = (f"Zincir analizi: {len(path_info['legs'])} bacak × ~1-2 dk "
                   "— her bacak ayrı analiz ediliyor (envanter bacaklar "
                   "arasında kaynağa dayalı evrilir)...")
    else:
        endpoint, timeout = "/analyze", 600
        spinner = ("Analiz sürüyor — veri tazeliği kontrolü → retrieval → "
                   "paket kesiştirme → LLM raporu → kaynak doğrulama "
                   "(~1-2 dk)...")
    with st.spinner(spinner):
        try:
            payload = {"target_version": target, "current_version": current,
                       "host": host}
            r = requests.post(f"{API_BASE_URL}{endpoint}",
                              json=payload, timeout=timeout)
        except requests.RequestException as exc:
            st.error(f"İstek başarısız: {exc}")
            st.stop()

    if r.status_code != 200:
        st.error(f"Analiz hatası ({r.status_code}): "
                 f"{r.json().get('detail', r.text)}")
        st.stop()

    # tek görünüm kuralı: yeni sonuç eski modun raporunu temizler
    if chain_mode:
        st.session_state["chain_report"] = r.json()
        st.session_state.pop("report", None)
    else:
        st.session_state["report"] = r.json()
        st.session_state.pop("chain_report", None)

# --- Rapor görünümü ---
report = st.session_state.get("report")
if report:
    where = f"`{report['host']}`" if report.get("host") else "bu makine"
    st.subheader(f"📋 Rapor: {report['current_version']} → "
                 f"{report['target_version']} — hedef: {where}")

    # Zincir Aşama 1 — raporun kapsam sınırı (API'nin döndürdüğü upgrade_path
    # esas alınır: sunucu tek gerçek kaynak)
    up = report.get("upgrade_path")
    if up and up.get("path") and not up.get("is_direct"):
        st.warning(
            f"⚠️ **Resmi upgrade yolu: {' → '.join(up['path'])}** — bu rapor "
            f"yalnızca **{report['target_version']}** değişikliklerini kapsar; "
            f"ara sürümlerin ({', '.join(up['skipped_intermediates'])}) "
            "değişiklikleri dahil DEĞİL.")

    render_report(report)

# --- Zincir raporu görünümü (Aşama 2): bacak bacak sekmeler ---
chain = st.session_state.get("chain_report")
if chain:
    where = f"`{chain['host']}`" if chain.get("host") else "bu makine"
    st.subheader(f"🔗 Zincir raporu: "
                 f"{' → '.join(chain['upgrade_path']['path'])} — hedef: {where}")

    if chain.get("error"):
        e = chain["error"]
        st.error(f"⛔ Zincir {e['leg'][0]}→{e['leg'][1]} bacağında durdu: "
                 f"{e['detail']} — aşağıda tamamlanan bacaklar gösteriliyor "
                 "(kısmi sonuç, dürüstçe işaretli).")
    for w in chain.get("warnings", []):
        st.warning(w)

    tabs = st.tabs([f"{l['from_version']} → {l['to_version']}"
                    for l in chain["legs"]])
    for tab, leg in zip(tabs, chain["legs"]):
        with tab:
            removed = leg["evolution"]["removed"]
            if removed:
                # bu bacağın (hedef sürümün) notlarında AÇIKÇA kalkan paketler —
                # sonraki bacağın envanterine taşınmazlar
                st.info(" **Bu bacağın release notes'una göre kalkan "
                        "paketler** (sonraki bacağa taşınmaz): "
                        + ", ".join(f"`{r['package']}`" for r in removed))
                with st.expander("Kaldırma kanıtları (release notes'tan birebir)"):
                    for r in removed:
                        st.markdown(f"- `{r['package']}` — `{r['chunk_id']}`: "
                                    f"“{r['quote']}”")
            with st.expander(f"Bu bacağa giren envanter "
                             f"({leg['inventory_size']} paket)"):
                st.code("\n".join(leg["inventory"]) or "(boş)")
            render_report(leg["report"])

    st.caption("ℹ️ " + chain["evolution_disclaimer"])
