# Lipsync Pipeline

> Audio + alignment + face animation → hosted/offline LipSync Reader or narration-only EPUB.

**Source:** [`screencastgen/pipelines/lipsync.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/pipelines/lipsync.py)

---

## Function

### `run_lipsync_pipeline(request, reporter, backend_factory) -> PipelineRunResult`
Full pipeline: synthesize voice-cloned audio, align words, generate lip-synced
face videos per chunk/page, then build the requested output format.

---

## Steps

```
1. Validate document + ref_video exist; ref_audio is optional when the reference video contains usable speech audio
2. Create TTS backend               ← TTS Registry
3. Extract and chunk                 ← Pipeline Common
   └── EPUB/reader: page-aware chunking
4. Validate and synthesize           ← Pipeline Common
5. Align chunks                      ← Pipeline Common → Aligner
6. For each chunk:
   ├── Loop ref_video to audio duration
   └── Generate lip-sync video       ← Lipsync Facade or Remote GPU Client
7. Build output:
   ├── reader: presenter.mp4 + Reader Assets
   └── EPUB: EPUB Builder
```

When the PDF page-image path is active, the same bbox-matching and oversampled page-rendering logic used by [Highlight Pipeline](highlight-pipeline.md) is reused before the face clip is composited.

---

## Configuration

Key fields from [LipsyncPipelineRequest](pipeline-types.md):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ref_video` | `str` | — | Reference face video path |
| `ref_audio` | `str` | `None` | Optional reference voice audio path |
| `lipsync_provider` | `str` | `"auto"` | Provider (`auto` or `latentsync`); auto currently resolves to LatentSync |
| `face_position` | `str` | `"bottom-right"` | Presenter position |
| `face_scale` | `float` | 0.22 | Presenter scale for docked corner layouts |
| `latentsync_preset` | `str` | `"quality"` | LatentSync quality preset |

Inherits all fields from [HighlightPipelineRequest](pipeline-types.md).

`format` controls the final artifact:

| Format | Output |
|--------|--------|
| `reader` | `<document>_reader.zip` plus hosted `reader_manifest.json`, audio, page images, and `presenter.mp4`; this is the default and recommended output |
| `epub` | EPUB3 text and narration with Media Overlays; presenter video is intentionally omitted |

## Progress And Cancellation

Long lip-sync runs emit structured page events through [Pipeline Events](pipeline-events.md):

| Event | Meaning |
|-------|---------|
| `page_start` | A page/chunk is being submitted to local or remote lip-sync |
| `page_progress` | Remote job poll returned elapsed GPU time |
| `page_done` | Page completed and its elapsed seconds were recorded |

The web worker passes `should_cancel` into `PipelineReporter`. For remote runs,
cancellation requests are forwarded to the GPU server's
`/lipsync/{id}/cancel` endpoint, and the pipeline abandons the active page from
its perspective. Local provider calls are not interrupted; the stop is observed
before starting the next page.

If at least one page finished, the reader or EPUB output is built from the
completed prefix. Reader presenter video is rebuilt instead of reusing a cached
full-length presenter. A stop before the first completed page fails because
there is no usable output.

Successful result metadata includes:

| Key | Meaning |
|-----|---------|
| `lipsync_stopped_early` | Whether cancellation shortened the run |
| `lipsync_pages_completed` | Number of pages included in the output |
| `lipsync_pages_total` | Original page count |
| `lipsync_page_times` | Completed-page durations in seconds |

## Reader Bundle

For `format="reader"`, the pipeline:

1. Normalizes each presenter chunk to the exact chunk-audio duration.
2. Concatenates chunks into `presenter.mp4`.
3. Calls [build_reader_assets()](../core/reader-assets.md) to create `reader_manifest.json`, `reader_audio.mp3`, and optional PDF page images.
4. Packages the assets with a serverless `index.html` as `<document>_reader.zip`.
5. Warns when presenter duration and reader manifest duration drift by more than 50 ms.

---

## Dependencies

```
Lipsync Pipeline
├── Pipeline Common        (extract, chunk, validate, synthesize, align, bbox extraction)
├── Pipeline Types         (LipsyncPipelineRequest, PipelineRunResult)
├── Highlight Pipeline     (parse_resolution)
├── Page Renderer          (PDF page-image rendering, preferred for PDFs)
├── Highlight Renderer     (plain-text fallback renderer)
├── Word Matcher           (maps aligned words to PDF bboxes)
├── Lipsync Facade         (generate_lipsync_video)
├── Remote GPU Client      (remote_generate_lipsync)
├── Video Composer         (compose_lipsync_video)
├── EPUB Builder           (EPUB3 assembly)
├── Reader Assets          (browser reader bundle)
└── TTS Registry           (create backend)
```

---

## See Also

- [Highlight Pipeline](highlight-pipeline.md) — Simpler pipeline (no face animation)
- [Lipsync Facade](../core/lipsync-facade.md) — Lip-sync generation API
- [LatentSync Provider](../providers/latent-sync-provider.md) — Primary lip-sync engine
- [Data Flow](../../concepts/data-flow.md) — Lipsync pipeline flow diagram
