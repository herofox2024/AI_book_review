"""核心层：配置、解析、摘要、风格、生成。"""

from .config import Settings, load_settings, PRESETS, PROJECT_ROOT, CONFIG_PATH
from .models import Book, Chapter, BookDigest
from .llm import LLMClient, LLMError
from .db import DB
from .chunker import chunk_book, Chunk
from .digest import DigestBuilder
from .style import StyleAnalyzer, compute_stats, load_samples_from_paths
from .generator import ReviewGenerator
from .prompts import LENGTH_PRESETS, FOCUS_PRESETS

__all__ = [
    "Settings", "load_settings", "PRESETS", "PROJECT_ROOT", "CONFIG_PATH",
    "Book", "Chapter", "BookDigest",
    "LLMClient", "LLMError", "DB",
    "chunk_book", "Chunk", "DigestBuilder",
    "StyleAnalyzer", "compute_stats", "load_samples_from_paths",
    "ReviewGenerator", "LENGTH_PRESETS", "FOCUS_PRESETS",
]
