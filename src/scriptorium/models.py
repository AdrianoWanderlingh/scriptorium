"""Lazily loaded ONNX models (CPU only): multilingual embedder and cross-encoder reranker."""

from __future__ import annotations

import os
import warnings
from functools import lru_cache

import numpy as np

from .config import EMBED_MODEL, EMBED_SPECS, MODEL_CACHE, RERANK_MODEL, THREADS

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
warnings.filterwarnings("ignore", module="fastembed")
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")

SPEC = EMBED_SPECS[EMBED_MODEL]


@lru_cache(maxsize=1)
def _embedder():
    from fastembed import TextEmbedding

    if SPEC.get("custom"):
        from fastembed.common.model_description import ModelSource, PoolingType

        if EMBED_MODEL not in {m["model"] for m in TextEmbedding.list_supported_models()}:
            TextEmbedding.add_custom_model(
                model=EMBED_MODEL,
                pooling=PoolingType.MEAN,
                normalization=True,
                sources=ModelSource(hf=EMBED_MODEL),
                dim=SPEC["dim"],
                model_file="onnx/model.onnx",
            )
    if SPEC.get("local_repo"):
        # onnxruntime refuses external weight files reached through the HF cache's symlinks,
        # so models with `.onnx_data` are downloaded into a plain directory.
        from huggingface_hub import snapshot_download

        local = MODEL_CACHE / "local" / EMBED_MODEL.split("/")[-1]
        if not (local / "onnx" / "model.onnx_data").exists():
            snapshot_download(
                SPEC["local_repo"],
                local_dir=str(local),
                allow_patterns=["onnx/model.onnx", "onnx/model.onnx_data", "*.json", "tokenizer*"],
            )
        return TextEmbedding(EMBED_MODEL, threads=THREADS, specific_model_path=str(local))
    return TextEmbedding(EMBED_MODEL, threads=THREADS, cache_dir=str(MODEL_CACHE))


@lru_cache(maxsize=1)
def _reranker():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(RERANK_MODEL, threads=THREADS, cache_dir=str(MODEL_CACHE))


def embed_passages(texts: list[str], titles: list[str] | None = None, batch_size: int = 4) -> np.ndarray:
    """Small batches: chunks vary in length and padding to the longest dominates CPU time."""
    titles = titles or ["none"] * len(texts)
    docs = [SPEC["passage"].format(title=h, text=t) for t, h in zip(texts, titles, strict=True)]
    return np.asarray(list(_embedder().embed(docs, batch_size=batch_size)), dtype=np.float32)


def embed_queries(texts: list[str]) -> np.ndarray:
    return np.asarray(list(_embedder().embed([SPEC["query"].format(text=t) for t in texts])), dtype=np.float32)


def rerank(query: str, texts: list[str], max_chars: int = 1600) -> list[float]:
    if not texts:
        return []
    return [float(s) for s in _reranker().rerank(query, [t[:max_chars] for t in texts], batch_size=8)]
