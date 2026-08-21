"""M4 / A3-A4 — LangGraph tanımı ve analyze() giriş noktası.

Akış (v1 = tek LTS atlaması):
  detect → refresh → retrieve_general → package_intersect → draft_report → grounding

LLM yalnızca draft_report'ta; grounding dahil geri kalan her adım deterministik.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from src.agent.grounding import node_grounding
from src.agent.nodes import (
    node_detect, node_draft_report, node_package_intersect,
    node_refresh, node_retrieve_general,
)
from src.remote.ssh_runner import is_reachable


class AgentState(TypedDict, total=False):
    host: str | None        # None → lokal analiz; "kullanici@ip" → SSH ile uzak (v2)
    current_version: str
    target_version: str
    packages: list          # None → otomatik envanter; M8'de sahte liste enjekte edilebilir
    warnings: list
    freshness: dict
    general_chunks: list
    package_candidates: list
    package_hits: dict
    draft_summary: str
    draft_claims: list
    used_model: str
    report: dict


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("detect", node_detect)
    g.add_node("refresh", node_refresh)
    g.add_node("retrieve_general", node_retrieve_general)
    g.add_node("package_intersect", node_package_intersect)
    g.add_node("draft_report", node_draft_report)
    g.add_node("grounding", node_grounding)

    g.add_edge(START, "detect")
    g.add_edge("detect", "refresh")
    g.add_edge("refresh", "retrieve_general")
    g.add_edge("retrieve_general", "package_intersect")
    g.add_edge("package_intersect", "draft_report")
    g.add_edge("draft_report", "grounding")
    g.add_edge("grounding", END)
    return g.compile()


_graph = None


def analyze(target_version: str, current_version: str | None = None,
            packages: list[str] | None = None,
            host: str | None = None) -> dict:
    """Uçtan uca analiz: rapor sözlüğü döner.

    current_version verilmezse sistemden (host verildiyse uzak sistemden)
    tespit edilir; packages verilmezse apt-mark envanteri kullanılır
    (M8: sahte liste enjekte edilebilir). host=None → lokal (eski davranış).
    """
    global _graph
    if _graph is None:
        _graph = build_graph()

    # Reachability ÖN-KONTROLÜ (v2 kararı: graph node'u değil — routes.py'deki
    # Ollama ön-kontrol deseninin simetriği). Erişilemeyen hedef için LLM'i
    # hiç çağırmadan dur: "uydurma yok"un bağlantı katmanı karşılığı.
    # ConnectionError → API'de 502'ye map'lenir (RuntimeError → 500'den ayrışır).
    if host and not is_reachable(host):
        raise ConnectionError(f"Hedef sunucuya bağlanılamadı: {host}")

    state: AgentState = {"target_version": target_version, "host": host}
    if current_version:
        state["current_version"] = current_version
    if packages is not None:
        state["packages"] = packages

    final = _graph.invoke(state)
    return final["report"]
