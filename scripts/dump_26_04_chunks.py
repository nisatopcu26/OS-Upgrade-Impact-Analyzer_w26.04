import json
from src.rag.chunking import chunk_release_notes
from src.rag.embeddings import count_tokens

with open("data/processed/26.04.json") as f:
    envelope = json.load(f)

chunks = chunk_release_notes(envelope, count_tokens)

out = [
    {"id": c.id, "text": c.text, "metadata": c.metadata}
    for c in chunks
]

with open("data/processed/26.04_chunks_dump.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(f"Toplam chunk: {len(out)}")
