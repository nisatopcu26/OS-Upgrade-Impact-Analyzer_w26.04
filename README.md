# OS Upgrade Impact Analyzer

A hallucination-free RAG system that answers one question before an Ubuntu LTS
upgrade: **"What will break on this machine?"**

The tool detects the target system (locally or over SSH, agentless), extracts
its manually installed packages, reads the official Ubuntu release notes, and
generates a machine-specific impact report written by a fully local LLM. Every
sentence in the report is mechanically verified against its cited official
source; claims that cannot be proven are rejected and disclosed openly instead
of being silently dropped.

## Key Properties

- **No hallucination by design.** Every claim must cite a source chunk. A
  three-layer verification cascade (source attribution, lexical entity check,
  semantic similarity with a calibrated threshold) rejects anything unproven.
- **Fully local.** The LLM (qwen2.5:7b via Ollama) and the embedding model run
  on the control node. No inventory data ever leaves the machine.
- **Agentless remote analysis.** Only two read-only commands run on the target
  over SSH; all SSH access passes through a single command-injection-hardened
  gate, validated again at the API boundary.
- **Chain upgrades.** Multi-step LTS paths (e.g. 18.04 to 24.04) are analyzed
  leg by leg, with the package inventory evolving between legs only on
  source-cited removal evidence.
- **Validated against reality.** Lab VMs were actually upgraded and compared
  with the reports: zero false alarms across three upgrade legs; the package
  flagged by the report was the one that blocked the real upgrade.

## Architecture

```
detect_os() + apt-mark showmanual + target version
        |
        v
Agent (LangGraph, 6 nodes)
  freshness check -> re-scrape if stale (scraper as a tool)
  retrieval (ChromaDB, 328 chunks)
  package intersection (lexical pre-filter -> targeted RAG)
        |
        v
Report draft  (structured claims with chunk_id citations)  <- the only LLM step
        |
        v
Grounding     (4 mechanical checks, RED/FLAG verdicts)
        |
        v
FastAPI (REST) -> Streamlit (UI)
```

| Module | Responsibility | Uses an LLM |
|---|---|---|
| `src/detector/` | OS detection, package inventory (local/SSH) | No |
| `src/scraper/` | Release notes collection, freshness/TTL cache | No |
| `src/rag/` | Token-based chunking, embeddings, vector store | No |
| `src/agent/` | LangGraph flow, report drafting, grounding | Draft node only |
| `src/api/` | FastAPI service | No |
| `src/ui/` | Streamlit interface | No |
| `src/remote/` | Agentless SSH execution, injection protection | No |
| `src/upgrade_path/` | LTS chain path computation, inventory evolution | No |

## Requirements

- Python 3.10 or newer; Ubuntu LTS targets 18.04 through 24.04
- [Ollama](https://ollama.com) with the `qwen2.5:7b` model pulled
- Approximately 2 GB of disk space for models and the vector index

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # adjust if needed
ollama pull qwen2.5:7b
```

## Usage

```bash
# Start the API (port 8010) and the UI (port 8501)
uvicorn src.api.main:app --port 8010
streamlit run src/ui/app.py

# Quick check without the UI:
curl -X POST http://localhost:8010/analyze \
  -H 'Content-Type: application/json' \
  -d '{"target_version": "24.04"}'

# Remote analysis (SSH key required; nothing is installed on the target):
curl -X POST http://localhost:8010/analyze \
  -H 'Content-Type: application/json' \
  -d '{"target_version": "24.04", "host": "user@192.168.1.10"}'
```

For remote targets, install your SSH key with `ssh-copy-id user@host` and
optionally copy `config/hosts.json.example` to `config/hosts.json` to add
labeled servers to the UI dropdown. `hosts.json` is personal configuration and
is not tracked by git.

Endpoints: `/detect`, `/packages`, `/versions`, `/analyze`, `/analyze-chain`.
Error handling is explicit: unsupported versions return 422, an unreachable
Ollama returns 503 before any LLM call, and an unreachable SSH target returns
502.

## Testing

```bash
python -m pytest -q
```

112 tests, including adversarial scenarios (fabricated chunk ids, unsourced
claims, irrelevant citations) that assert the verifier rejects them.
Integration tests that require live VMs carry the `lab` marker and are skipped
automatically when the lab is offline. No test requires a real model or a
network connection; heavy dependencies are injected and mocked.

## Configuration

Central settings live in `config/settings.py` and can be overridden through
environment variables: the embedding model profile
(`BAAI/bge-small-en-v1.5`, similarity threshold 0.60), the LLM model, cache
TTL, and service ports. Supported versions and their source URLs are defined
in `config/versions.json`.

## License

MIT. See [LICENSE](LICENSE).
