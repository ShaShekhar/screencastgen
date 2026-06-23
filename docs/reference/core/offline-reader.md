# Offline Reader

> Packages hosted reader assets into a standalone ZIP that opens without a web server.

**Source:** [`screencastgen/offline_reader.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/offline_reader.py)

---

## Function

### `build_offline_reader_archive(manifest_path, output_path) -> str`

Loads `reader_manifest.json`, validates that every referenced audio, presenter,
and page-image asset exists beneath the manifest directory, then writes an
archive containing:

- `index.html` with the manifest embedded as JSON, so local playback does not
  depend on `fetch()` or an HTTP server
- `reader_manifest.json`
- `reader_audio.mp3`
- optional `presenter.mp4`
- optional rendered images under `pages/`

The archive is assembled through a temporary file and atomically moved into
place. Assets outside the reader output directory are rejected.

The embedded viewer provides synchronized word highlighting, seeking, playback
speed, auto-scroll, document page images, theme selection, and a draggable,
resizable presenter.

## See Also

- [Reader Assets](reader-assets.md) — Produces the manifest and media inputs
- [Lipsync Pipeline](../pipelines/lipsync-pipeline.md) — Builds the ZIP as its default artifact
- [Reader Page](../web/frontend/reader-page.md) — Hosted React reader
