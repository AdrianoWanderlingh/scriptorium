"""Lazily loaded ONNX models (CPU only): multilingual embedder and cross-encoder reranker."""

from __future__ import annotations

import os
import warnings
from functools import lru_cache

import numpy as np

from .config import EMBED_DIM, EMBED_MODEL, MODEL_CACHE, RERANK_MODEL, THREADS

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
warnings.filterwarnings("ignore", module="fastembed")
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")

E5_MODELS = {"intfloat/multilingual-e5-small": "onnx/model.onnx", "intfloat/multilingual-e5-base": "onnx/model.onnx"}


@lru_cache(maxsize=1)
def _embedder():
    from fastembed import TextEmbedding

    if EMBED_MODEL in E5_MODELS:
        from fastembed.common.model_description import ModelSource, PoolingType

        known = {m["model"] for m in TextEmbedding.list_supported_models()}
        if EMBED_MODEL not in known:
            TextEmbedding.add_custom_model(
                model=EMBED_MODEL,
                pooling=PoolingType.MEAN,
                normalization=True,
                sources=ModelSource(hf=EMBED_MODEL),
                dim=EMBED_DIM,
                model_file=E5_MODELS[EMBED_MODEL],
            )
    return TextEmbedding(EMBED_MODEL, threads=THREADS, cache_dir=str(MODEL_CACHE))


@lru_cache(maxsize=1)
def _reranker():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(RERANK_MODEL, threads=THREADS, cache_dir=str(MODEL_CACHE))


def _prefix(kind: str) -> str:
    return f"{kind}: " if EMBED_MODEL in E5_MODELS else ""


def embed_passages(texts: list[str], batch_size: int = 16) -> np.ndarray:
    prefix = _prefix("passage")
    vecs = _embedder().embed([prefix + t for t in texts], batch_size=batch_size)
    return np.asarray(list(vecs), dtype=np.float32)


def embed_queries(texts: list[str]) -> np.ndarray:
    prefix = _prefix("query")
    return np.asarray(list(_embedder().embed([prefix + t for t in texts])), dtype=np.float32)


def rerank(query: str, texts: list[str]) -> list[float]:
    if not texts:
        return []
    return [float(s) for s in _reranker().rerank(query, [t[:900] for t in texts], batch_size=8)]
