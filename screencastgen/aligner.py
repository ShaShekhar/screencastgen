"""Word-level audio alignment facade."""

from __future__ import annotations

from typing import List

from .providers.align import (
    DEFAULT_ALIGNMENT_PROVIDER,
    align_with_provider,
    get_alignment_provider_names,
    get_default_alignment_provider,
)
from .types import WordTiming


def align_chunk(
    audio_path: str,
    text: str,
    *,
    provider: str = DEFAULT_ALIGNMENT_PROVIDER,
    language: str = "en-US",
    device: str = "auto",
) -> List[WordTiming]:
    """Align *text* against *audio_path* via the selected provider."""
    return align_with_provider(
        provider,
        audio_path,
        text,
        language=language,
        device=device,
    )
