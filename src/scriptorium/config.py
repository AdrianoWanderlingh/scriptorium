"""Paths, model choices and per-library settings."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOME = Path(os.environ.get("SCRIPTORIUM_HOME", PROJECT_ROOT / "libraries"))

# Prompt formats are each model's documented retrieval convention.
EMBED_SPECS = {
    "google/embeddinggemma-300m": {
        "dim": 768,
        "query": "task: search result | query: {text}",
        "passage": "title: {title} | text: {text}",
        "local_repo": "onnx-community/embeddinggemma-300m-ONNX",
    },
    "intfloat/multilingual-e5-small": {
        "dim": 384,
        "query": "query: {text}",
        "passage": "passage: {title}\n{text}",
        "custom": True,
    },
}
EMBED_MODEL = os.environ.get("SCRIPTORIUM_EMBED_MODEL", "google/embeddinggemma-300m")
EMBED_DIM = EMBED_SPECS[EMBED_MODEL]["dim"]
RERANK_MODEL = os.environ.get("SCRIPTORIUM_RERANK_MODEL", "jinaai/jina-reranker-v2-base-multilingual")
MODEL_CACHE = Path(os.environ.get("SCRIPTORIUM_MODEL_CACHE", Path.home() / ".cache" / "scriptorium" / "models"))
THREADS = int(os.environ.get("SCRIPTORIUM_THREADS", max(1, (os.cpu_count() or 4) - 2)))

SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".pdf",
    ".html",
    ".htm",
    ".docx",
    ".doc",
    ".pptx",
    ".xlsx",
    ".xls",
    ".csv",
    ".json",
    ".xml",
    ".epub",
    ".rtf",
    ".odt",
}


@dataclass
class LibraryConfig:
    name: str
    description: str = ""
    topic: str = ""
    fts_language: str = "English"
    chunk_chars: int = 1400
    embed_model: str = ""
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> LibraryConfig:
        return cls(**json.loads(path.read_text()))

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))
