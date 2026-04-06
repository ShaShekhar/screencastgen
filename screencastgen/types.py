"""Shared data types for screencastgen."""

from dataclasses import dataclass, field
from typing import List, Protocol


@dataclass
class WordTiming:
    """A single word with its timing in the audio."""

    word: str
    start: float  # seconds from start of chunk audio
    end: float  # seconds from start of chunk audio
    page: int = 0  # source PDF page (1-indexed), 0 = unknown


@dataclass
class AlignedChunk:
    """A text chunk with its audio and word-level timing."""

    chunk_num: int
    text: str
    audio_path: str
    words: List[WordTiming] = field(default_factory=list)
    offset: float = 0.0  # seconds from start of full concatenated audio
    pages: List[int] = field(default_factory=list)  # PDF pages this chunk spans


class TTSBackend(Protocol):
    """Protocol for TTS backends."""

    @property
    def max_chunk_bytes(self) -> int:
        """Maximum UTF-8 byte length per chunk for this backend."""
        ...

    @property
    def output_format(self) -> str:
        """File extension for synthesized audio (e.g. 'mp3', 'wav')."""
        ...

    def synthesize(self, text: str, output_path: str) -> None: ...
