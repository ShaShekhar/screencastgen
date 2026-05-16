"""Processing state tracker for resumable chunk processing."""

import hashlib
import json
import os
from typing import Dict


def compute_chunk_hash(chunk: str) -> str:
    """Return an MD5 hex digest for *chunk* (used for change detection)."""
    return hashlib.md5(chunk.encode("utf-8")).hexdigest()


class ProcessingTracker:
    """Persist which chunks have been processed so runs can be resumed."""

    def __init__(self, filename: str = "processing_status.json"):
        self.filename = filename
        self.status: Dict = self._load()

    # -- persistence ----------------------------------------------------------

    def _load(self) -> Dict:
        if os.path.exists(self.filename) and os.path.getsize(self.filename) > 0:
            with open(self.filename, "r") as fh:
                data = json.load(fh)
            # Migrate old status files
            data.setdefault("aligned_chunks", {})
            data.setdefault("video_chunks", {})
            return data
        return {
            "total_chunks": 0,
            "processed_chunks": {},
            "failed_chunks": {},
            "chunk_hashes": {},
            "aligned_chunks": {},
            "video_chunks": {},
        }

    def save(self) -> None:
        with open(self.filename, "w") as fh:
            json.dump(self.status, fh, indent=2)

    # -- mutators -------------------------------------------------------------

    def mark_processed(self, chunk_num: int, chunk_hash: str, output_file: str) -> None:
        self.status["processed_chunks"][str(chunk_num)] = {
            "output_file": output_file,
            "chunk_hash": chunk_hash,
        }
        self.status["failed_chunks"].pop(str(chunk_num), None)
        self.save()

    def mark_failed(self, chunk_num: int, chunk_hash: str, error: str) -> None:
        self.status["failed_chunks"][str(chunk_num)] = {
            "error": error,
            "chunk_hash": chunk_hash,
        }
        self.save()

    # -- queries --------------------------------------------------------------

    def is_processed(self, chunk_num: int, chunk_hash: str) -> bool:
        entry = self.status["processed_chunks"].get(str(chunk_num))
        if entry is None:
            return False
        return entry.get("chunk_hash", "") == chunk_hash

    def mark_aligned(self, chunk_num: int, words: list) -> None:
        self.status["aligned_chunks"][str(chunk_num)] = {
            "words": [{"word": w.word, "start": w.start, "end": w.end} for w in words],
        }
        self.save()

    def is_aligned(self, chunk_num: int) -> bool:
        return str(chunk_num) in self.status["aligned_chunks"]

    def get_alignment(self, chunk_num: int) -> list:
        entry = self.status["aligned_chunks"].get(str(chunk_num))
        if entry is None:
            return []
        return entry["words"]

    def mark_video_rendered(self, chunk_num: int, video_path: str) -> None:
        self.status["video_chunks"][str(chunk_num)] = {"video_path": video_path}
        self.save()

    def is_video_rendered(self, chunk_num: int) -> bool:
        return str(chunk_num) in self.status["video_chunks"]

    def mark_epub_built(self) -> None:
        self.status["epub_built"] = True
        self.save()

    def is_epub_built(self) -> bool:
        return self.status.get("epub_built", False)

    def mark_presenter_built(self) -> None:
        self.status["presenter_built"] = True
        self.save()

    def is_presenter_built(self) -> bool:
        return self.status.get("presenter_built", False)

    def get_summary(self) -> Dict:
        total = self.status["total_chunks"]
        processed = len(self.status["processed_chunks"])
        failed = len(self.status["failed_chunks"])
        return {
            "total": total,
            "processed": processed,
            "failed": failed,
            "remaining": total - processed,
        }
