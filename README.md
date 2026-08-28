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
  flagged by the report was the one that blocked the real upgrade. A real
  24.04 -> 26.04 `do-release-upgrade` was also run on a cloned VM (206 new
  packages, 1405 upgrades, zero errors) to validate the newest LTS.
- **26.04 LTS support, measured.** Retrieval was validated with a 50-question
  golden set (recall@5 0.980, MRR 0.970) rather than assumed; a real grounding
  bug found during testing (a verb-to-noun derivation like `mitigate` ->
  `mitigation` was not recognized as a match) was fixed test-first.
- **Additional evidence layers.** Beyond release notes, the system cross-
  references apt Breaks/Conflicts/Replaces relations and Debian NEWS.Debian
  maintainer notes -- catching real-world blockers (e.g. a Samba AD-DC split)
  that release notes alone don't mention.
- **RHEL-family support (Rocky Linux).** The same architecture, unmodified,
  correctly detects and analyzes Rocky Linux (`ID_LIKE="rhel centos fedora"`)
  systems. A Rocky-specific scraper (GitHub-hosted markdown, no HTML parsing)
  feeds the same chunking/embedding/retrieval pipeline. Validated end-to-end
  against a real Rocky 9.8 -> 10.2 upgrade scenario on a real VM, with an
  adversarial test confirming the grounding layer rejects fabricated claims
  on RHEL-family content exactly as it does on Ubuntu.

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

- Python 3.10 or newer; Ubuntu LTS targets 18.04 through 26.04
- RHEL-family targets: Rocky Linux 9.x and 10.x (RHEL itself untested;
  Rocky does not support in-place major-version upgrades, so a genuine
  `leapp`-based upgrade test would require real RHEL)
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

130+ tests, including adversarial scenarios (fabricated chunk ids, unsourced
claims, irrelevant citations, and -- for the RHEL-family pipeline
specifically -- fabricated claims against real Rocky Linux content) that
assert the verifier rejects them. Integration tests that require live VMs
carry the `lab` marker and are skipped automatically when the lab is
offline. No test requires a real model or a network connection for the
non-`lab` suite; heavy dependencies are injected and mocked.

## Configuration

Central settings live in `config/settings.py` and can be overridden through
environment variables: the embedding model profile
(`BAAI/bge-small-en-v1.5`, similarity threshold 0.60), the LLM model, cache
TTL, and service ports. Supported versions and their source URLs are defined
in `config/versions.json`, including RHEL-family entries (`rocky-9.8`,
`rocky-10.2`) that point at Rocky Linux's GitHub-hosted markdown release
notes rather than a scraped HTML page.

## Known Limitations

- **A small number of retrieval queries do not surface their target chunk
  in the top 5 results** (e.g. "what Linux kernel version does Ubuntu 26.04
  ship?" -- the correct chunk ranks 7th). Root cause: sibling chunks from
  the same multi-chunk section contain unrelated version-number boilerplate
  ("Added in version 26.04") that superficially matches the query. Three
  independent fixes were attempted and rejected after measurement (stripping
  the boilerplate corpus-wide made results worse; a retrieval-time lexical
  penalty also made results worse) -- documented as an open issue rather
  than worked around.
- **RHEL-family support covers detection, package inventory, and the full
  report-generation pipeline, but not a genuine `leapp` major-version
  upgrade test** -- Rocky Linux does not support in-place major upgrades,
  so this would require real RHEL (a free Red Hat Developer subscription)
  rather than Rocky.

## License

MIT. See [LICENSE](LICENSE).
