"""263 token uyarisini veren chunk'i bul, MiniLM vs bge tokenizer farkini olc."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rag.embeddings import get_model

minilm = get_model("sentence-transformers/all-MiniLM-L6-v2")
bge = get_model("BAAI/bge-small-en-v1.5")

chunks = json.loads(Path("data/processed/26.04_chunks_dump.json").read_text())

print(f"bge max_seq_length: {bge.max_seq_length}")
print(f"minilm max_seq_length: {minilm.max_seq_length}")
print()

offenders = []
for c in chunks:
    text = c["text"]
    minilm_len = len(minilm.tokenizer.tokenize(text))
    bge_len = len(bge.tokenizer.tokenize(text))
    if bge_len > 250 or minilm_len > 250:
        offenders.append((c["id"], minilm_len, bge_len))

print(f"250 token sinirini asan chunk sayisi: {len(offenders)}")
for cid, m_len, b_len in offenders:
    print(f"  {cid}")
    print(f"    minilm_token={m_len}  bge_token={b_len}  fark={b_len - m_len}")
