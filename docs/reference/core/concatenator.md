# Concatenator

> Merges individual audio chunk files into a single output file.

**Source:** [`screencastgen/concatenator.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/concatenator.py)

---

## Function

### `concatenate(output_dir, dest, ext, files) -> str`
Merges `audio_chunk_*.{ext}` files into a single output file.

**Strategy:**
1. Tries `pydub` (preferred — handles format conversion)
2. Falls back to `ffmpeg` CLI if pydub is unavailable

**Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `output_dir` | `str` | Directory containing chunk files |
| `dest` | `str` | Output file path |
| `ext` | `str` | Audio extension (`wav`, `mp3`) |
| `files` | `List[str]` | Ordered list of chunk file paths |

**Returns:** Path to the merged output file.

---

## Dependencies

```
Concatenator
├── pydub         (preferred, deferred import)
├── ffmpeg CLI    (fallback)
└──▶ consumed by Audio Pipeline
```

---

## See Also

- [Audio Pipeline](../pipelines/audio-pipeline.md) — Calls concatenate as final step
- [Constants](constants.md) — `CHUNK_FILE_PATTERN` for file naming
