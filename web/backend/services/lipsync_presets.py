"""Bundled lip-sync presenter preset library."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional


PRESETS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "lipsync_presets")
)
MANIFEST_PATH = os.path.join(PRESETS_DIR, "manifest.json")


@dataclass
class LipsyncPreset:
    id: str
    name: str
    language: str
    description: str
    video_file: str
    audio_file: str
    ref_text: str

    @property
    def video_abs_path(self) -> str:
        return os.path.join(PRESETS_DIR, self.video_file)

    @property
    def audio_abs_path(self) -> str:
        return os.path.join(PRESETS_DIR, self.audio_file) if self.audio_file else ""

    @property
    def video_exists(self) -> bool:
        return os.path.isfile(self.video_abs_path)

    @property
    def audio_exists(self) -> bool:
        return bool(self.audio_file) and os.path.isfile(self.audio_abs_path)

    @property
    def exists(self) -> bool:
        return self.video_exists and (not self.audio_file or self.audio_exists)


def load_lipsync_presets() -> List[LipsyncPreset]:
    """Read the manifest and return all declared lip-sync presets."""
    if not os.path.isfile(MANIFEST_PATH):
        return []
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    out: List[LipsyncPreset] = []
    for entry in data.get("presets", []):
        try:
            out.append(
                LipsyncPreset(
                    id=str(entry["id"]),
                    name=str(entry["name"]),
                    language=str(entry.get("language", "en-US")),
                    description=str(entry.get("description", "")),
                    video_file=str(entry["video_file"]),
                    audio_file=str(entry.get("audio_file", "")),
                    ref_text=str(entry.get("ref_text", "")),
                )
            )
        except KeyError:
            continue
    return out


def get_lipsync_preset(preset_id: str) -> Optional[LipsyncPreset]:
    for preset in load_lipsync_presets():
        if preset.id == preset_id:
            return preset
    return None
