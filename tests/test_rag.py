"""M3 / R1 — Chunking testleri.

count_tokens enjekte edildiği için model YÜKLEMEDEN test edilir:
sahte sayaç = kelime sayısı (fake_counter). Gerçek tokenizer doğrulaması
Sprint R3'te build_index sonrası ayrıca yapılır.
"""

from src.rag.chunking import (
    Chunk, chunk_release_notes, chunk_section, clean_text, split_sentences,
)


def fake_counter(text: str) -> int:
    return len(text.split())


def make_envelope(sections):
    return {
        "version": "24.04",
        "source_url": "https://example.com/24.04/",
        "scraped_at": "2026-07-07T10:00:00",
        "sections": sections,
    }


def make_section(content, title="Known Issues¶", section_id="known-issues"):
    return {
        "version": "24.04",
        "section": title,
        "section_id": section_id,
        "content": content,
        "source_url": "https://example.com/24.04/",
    }


def test_short_section_single_chunk():
    env = make_envelope([make_section("This release has some known bugs listed here.")])
    chunks = chunk_release_notes(env, fake_counter, max_tokens=50)
    assert len(chunks) == 1
    assert chunks[0].id == "24.04_known-issues_0"


def test_paragraph_mark_cleaned():
    env = make_envelope([make_section("Bug list follows here now¶ with details.")])
    chunks = chunk_release_notes(env, fake_counter, max_tokens=50)
    assert "¶" not in chunks[0].text
    assert "¶" not in chunks[0].metadata["section_title"]


def test_long_section_splits_at_sentence_boundary():
    # 10 cümle x 10 kelime = 100 kelime; bütçe 30 → birden çok chunk
    sentence = "word one two three four five six seven eight nine."
    env = make_envelope([make_section(" ".join([sentence] * 10))])
    chunks = chunk_release_notes(env, fake_counter, max_tokens=30)
    assert len(chunks) > 1
    for c in chunks:
        assert fake_counter(c.text) <= 30
        # cümle ortasından kesilmedi: her chunk nokta ile bitiyor
        assert c.text.rstrip().endswith(".")


def test_oversized_sentence_hard_split():
    # Tek cümle 100 kelime, hiç nokta yok → sert bölme devreye girmeli
    giant = "pkg" + " libfoo-dev" * 99
    env = make_envelope([make_section(giant + ".")])
    chunks = chunk_release_notes(env, fake_counter, max_tokens=30)
    assert len(chunks) >= 3
    for c in chunks:
        assert fake_counter(c.text) <= 30   # hiçbir parça bütçeyi aşmaz


def test_metadata_complete_and_id_copied():
    env = make_envelope([make_section("Content sentence with enough words here.")])
    c = chunk_release_notes(env, fake_counter, max_tokens=50)[0]
    m = c.metadata
    assert m["id"] == c.id                      # id metadata'ya kopyalanır
    assert m["version"] == "24.04"
    assert m["section_id"] == "known-issues"
    assert m["section_title"] == "Known Issues"  # ¶ temiz
    assert m["source_url"].startswith("https://")
    assert m["scraped_at"] == "2026-07-07T10:00:00"  # zarftan geldi


def test_tiny_section_skipped():
    env = make_envelope([make_section("Too short.")])
    assert chunk_release_notes(env, fake_counter) == []


def test_missing_section_id_falls_back_to_slug():
    sec = make_section("Some meaningful content sentence goes here.",
                       title="Weird Title!", section_id=None)
    env = make_envelope([sec])
    c = chunk_release_notes(env, fake_counter, max_tokens=50)[0]
    assert c.id == "24.04_weird-title_0"


def test_title_prefix_included():
    env = make_envelope([make_section("The installer may crash on old hardware.")])
    c = chunk_release_notes(env, fake_counter, max_tokens=50)[0]
    assert c.text.startswith("Known Issues: ")


def test_sentence_split_basics():
    s = split_sentences("First sentence. Second one! Third? Done.")
    assert len(s) == 4


def test_clean_text_collapses_whitespace():
    assert clean_text("a\n\n b\t c") == "a b c"


# --- S1 (update_plan_3): model profili — koleksiyon + önek modeli izler -----

def test_embedding_profiles_consistent():
    """Profil tablosu değişmezleri: bge öneki sondaki boşluk DAHİL, minilm
    öneksiz; koleksiyon adları modele kilitli (S1 — 'geri dönüş tek satır')."""
    from config.settings import _PROFILES

    minilm = _PROFILES["sentence-transformers/all-MiniLM-L6-v2"]
    assert minilm["collection"] == "ubuntu_minilm"
    assert minilm["query_prefix"] == ""

    bge = _PROFILES["BAAI/bge-small-en-v1.5"]
    assert bge["collection"] == "ubuntu_bge"
    assert bge["query_prefix"] == (
        "Represent this sentence for searching relevant passages: ")
    assert bge["query_prefix"].endswith(": ")   # sondaki boşluk kırpılmamış


def test_unknown_embedding_model_rejected():
    """Bilinmeyen model → import anında açık ValueError (sessiz fallback yok):
    aksi hâlde yanlış koleksiyonda öneksiz arama sessizce çalışırdı."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = {**os.environ, "EMBEDDING_MODEL": "uydurma/model-v9"}
    r = subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        capture_output=True, text=True, timeout=60, env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert r.returncode != 0
    assert "Bilinmeyen embedding modeli" in r.stderr
