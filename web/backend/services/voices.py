"""Bundled reference-voice library.

Reads ``web/backend/voices/manifest.json`` to expose a curated set of
reference WAV clips that the UI offers as preset voices for the
"Highlight Text Audio" pipeline.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional


VOICES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "voices")
)
MANIFEST_PATH = os.path.join(VOICES_DIR, "manifest.json")


@dataclass
class BundledVoice:
    id: str
    name: str
    language: str
    description: str
    file: str
    ref_text: str

    @property
    def abs_path(self) -> str:
        return os.path.join(VOICES_DIR, self.file)

    @property
    def exists(self) -> bool:
        return os.path.isfile(self.abs_path)


def load_voices() -> List[BundledVoice]:
    """Read the manifest and return all declared voices.

    Voices whose backing WAV file is missing are still returned (UI can
    show them as unavailable) so the manifest is the source of truth.
    """
    if not os.path.isfile(MANIFEST_PATH):
        return []
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: List[BundledVoice] = []
    for entry in data.get("voices", []):
        try:
            out.append(
                BundledVoice(
                    id=str(entry["id"]),
                    name=str(entry["name"]),
                    language=str(entry.get("language", "en-US")),
                    description=str(entry.get("description", "")),
                    file=str(entry["file"]),
                    ref_text=str(entry.get("ref_text", "")),
                )
            )
        except KeyError:
            continue
    return out


def get_voice(voice_id: str) -> Optional[BundledVoice]:
    for v in load_voices():
        if v.id == voice_id:
            return v
    return None
