# Tracker

> Resumable processing state persistence via JSON file.

**Source:** [`screencastgen/tracker.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/tracker.py)

---

## Overview

`ProcessingTracker` persists chunk-level processing state to a JSON file (`processing_status.json`). This enables crash recovery — re-running a pipeline skips already-completed chunks. Chunks are keyed by `chunk_number + MD5 hash`, so content changes invalidate stale entries.

---

## Class: `ProcessingTracker`

### Constructor
```python
ProcessingTracker(status_file: str)
```

### Chunk Processing
| Method | Description |
|--------|-------------|
| `mark_processed(chunk_num, chunk_hash, output_file)` | Record successful chunk synthesis |
| `mark_failed(chunk_num, chunk_hash, error)` | Record chunk failure with error message |
| `is_processed(chunk_num, chunk_hash) -> bool` | Check if chunk already completed |

### Alignment
| Method | Description |
|--------|-------------|
| `mark_aligned(chunk_num, words)` | Store word-level timing data |
| `is_aligned(chunk_num) -> bool` | Check if alignment exists |
| `get_alignment(chunk_num) -> List[dict]` | Retrieve stored word timings |

### Video Rendering
| Method | Description |
|--------|-------------|
| `mark_video_rendered(chunk_num, video_path)` | Record lip-sync video completion |
| `is_video_rendered(chunk_num) -> bool` | Check if video exists |

### EPUB
| Method | Description |
|--------|-------------|
| `mark_epub_built()` | Record EPUB assembly completion |
| `is_epub_built() -> bool` | Check if EPUB was built |

### Persistence
| Method | Description |
|--------|-------------|
| `_load()` | Load state from JSON file |
| `save()` | Write state to JSON file |
| `get_summary() -> dict` | Return processed/failed/remaining counts |

### Hashing
| Function | Description |
|----------|-------------|
| `compute_chunk_hash(text: str) -> str` | MD5 hash of chunk text for cache key |

---

## State File Format

```json
{
  "chunks": {
    "0001_a1b2c3d4": {
      "status": "processed",
      "output_file": "audio_chunk_0001.wav"
    }
  },
  "alignments": {
    "1": [{"word": "Hello", "start": 0.0, "end": 0.5}]
  },
  "videos": {
    "1": "lipsync_chunk_0001.mp4"
  },
  "epub_built": false
}
```

---

## Dependencies

```
Tracker
├── hashlib (MD5)
├── json (persistence)
└──▶ consumed by Pipeline Common
     ├── Audio Pipeline
     ├── Highlight Pipeline
     └── Lipsync Pipeline
```

---

## See Also

- [Pipeline Common](../pipelines/pipeline-common.md) — Creates and uses tracker instances
- [Data Flow](../../concepts/data-flow.md) — Where tracker fits in the pipeline
