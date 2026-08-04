"""M3 / Sprint R2 — Embedding katmanı.

Chunk metinlerini Sentence-Transformers ile vektöre çevirir.

- Model global cache'lenir (get_model): yükleme pahalı (~saniyeler),
  süreç başına bir kez yapılır.
- normalize_embeddings=True: vektörler birim uzunlukta → kosinüs benzerliği
  basit dot product'a iner (Chroma cosine metriğiyle tutarlı).
- count_tokens: modelin KENDİ tokenizer'ıyla gerçek token sayısı — chunking'e
  enjekte edilir (kelime-proxy tahmini yok, sessiz kırpma riski yok).
- R5 model kıyası için model adı parametreli; varsayılan config'ten gelir.
"""

from sentence_transformers import SentenceTransformer

from config.settings import EMBEDDING_MODEL

_models: dict[str, SentenceTransformer] = {}


def get_model(model_name: str = EMBEDDING_MODEL) -> SentenceTransformer:
    """Modeli bir kez yükler, sonraki çağrılarda cache'ten döner."""
    if model_name not in _models:
        _models[model_name] = SentenceTransformer(model_name)
    return _models[model_name]


def embed_texts(texts: list[str], model_name: str = EMBEDDING_MODEL):
    """Metin listesini normalize edilmiş vektör matrisine çevirir."""
    model = get_model(model_name)
    return model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=False,
    )


def count_tokens(text: str, model_name: str = EMBEDDING_MODEL) -> int:
    """Modelin kendi tokenizer'ıyla GERÇEK token sayısı.

    Not: özel tokenlar ([CLS]/[SEP]) sayılmaz; chunking bütçesi (250) bunların
    payını (+2) zaten sınırın (256) altında bırakır.
    """
    return len(get_model(model_name).tokenizer.tokenize(text))
