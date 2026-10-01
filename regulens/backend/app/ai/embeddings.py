import threading

import numpy as np

from app.core.config import settings

_model = None
_lock = threading.Lock()
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def _get_model():
    global _model
    with _lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        return _model


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Passage/document embeddings (normalised)."""
    if not texts:
        return []
    vecs = _get_model().encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vecs, dtype=float).tolist()


def embed_queries(texts: list[str]) -> list[list[float]]:
    return embed_texts([BGE_QUERY_PREFIX + t for t in texts])


def embed_query(text: str) -> list[float]:
    return embed_queries([text])[0]
