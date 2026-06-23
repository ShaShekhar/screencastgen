# Constants

> System-wide byte limits, default values, and file patterns.

**Source:** [`screencastgen/constants.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/constants.py)

---

## TTS Limits

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_CHUNK_BYTES` | 4900 | Default max UTF-8 bytes per chunk |
| `MAX_TTS_BYTES` | 5000 | Hard limit for TTS input validation |
| `MAX_SENTENCE_BYTES` | 850 | Max bytes before force-splitting a sentence |

---

## Defaults

| Constant | Value | Description |
|----------|-------|-------------|
| `DEFAULT_LANGUAGE` | `"en-US"` | Default TTS language |
| `DEFAULT_OUTPUT_DIR` | `"audio"` | Default output directory name |

---

## Video Defaults

| Constant | Value | Description |
|----------|-------|-------------|
| `DEFAULT_VIDEO_WIDTH` | 1280 | Default video width (px) |
| `DEFAULT_VIDEO_HEIGHT` | 720 | Default video height (px) |
| `DEFAULT_VIDEO_FPS` | 24 | Default frames per second |

---

## EPUB Defaults

| Constant | Value | Description |
|----------|-------|-------------|
| `EPUB_AUDIO_FORMAT` | `"mp3"` | Audio format inside EPUB |
| `EPUB_CHAPTER_DIR` | `"chapters"` | Chapter directory within EPUB |

---

## File Patterns

| Constant | Pattern | Used By |
|----------|---------|---------|
| `CHUNK_FILE_PATTERN` | `audio_chunk_{num:04d}.{ext}` | [Pipeline Common](../pipelines/pipeline-common.md), [Concatenator](concatenator.md) |
| `VIDEO_CHUNK_FILE_PATTERN` | `lipsync_chunk_{num:04d}.mp4` | [Lipsync Pipeline](../pipelines/lipsync-pipeline.md) |

---

## Usage

These constants serve as defaults — each [TTSBackend](types.md) declares its own `max_chunk_bytes` property that may differ. [Text Processing](text-processing.md) and [Pipeline Common](../pipelines/pipeline-common.md) reference these for validation.

---

## See Also

- [Types](types.md) — `TTSBackend` protocol with per-backend limits
- [Text Processing](text-processing.md) — Uses byte limits for chunking
- [TTS Base](../providers/tts-base.md) — `BackendSpec` can override limits
