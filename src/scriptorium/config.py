"""Paths, model choices and per-library settings."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOME = Path(os.environ.get("SCRIPTORIUM_HOME", PROJECT_ROOT / "libraries"))

EMBED_MODEL = os.environ.get("SCRIPTORIUM_EMBED_MODEL", "intfloat/multilingual-e5-small")
EMBED_DIM = 384
RERANK_MODEL = os.environ.get(
    "SCRIPTORIUM_RERANK_MODEL", "jinaai/jina-reranker-v2-base-multilingual"
)
MODEL_CACHE = Path(os.environ.get("SCRIPTORIUM_MODEL_CACHE", Path.home() / ".cache" / "scriptorium" / "models"))
THREADS = int(os.environ.get("SCRIPTORIUM_THREADS", max(1, (os.cpu_count() or 4) - 2)))

SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".pdf", ".html", ".htm", ".docx", ".doc", ".pptx",
    ".xlsx", ".xls", ".csv", ".json", ".xml", ".epub", ".rtf", ".odt",
}


@dataclass
class LibraryConfig:
    name: str
    description: str = ""
    topic: str = ""
    fts_language: str = "English"
    chunk_chars: int = 1400
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "LibraryConfig":
        return cls(**json.loads(path.read_text()))

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))
