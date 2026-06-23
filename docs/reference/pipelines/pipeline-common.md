# Pipeline Common

> Shared helper functions used by the document pipeline runners.

**Source:** [`screencastgen/pipelines/common.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/pipelines/common.py)

---

## Overview

Central module containing the shared steps used by audio, highlight, and lip-sync runners: extract, chunk, validate, synthesize, and align. The prompt-driven [Visualization Pipeline](visualization-pipeline.md) only uses the reporter helper.

---

## Functions

### Setup Helpers

| Function | Description |
|----------|-------------|
| `get_reporter(reporter) -> PipelineReporter` | Ensure a reporter instance exists |
| `prepare_tracker(args) -> ProcessingTracker` | Create tracker and handle `--clean` |
| `create_tts_backend(args, invocation)` | Validate and instantiate the requested TTS backend |
| `build_title(pdf_path) -> str` | Convert filename to title string |
| `status_path(output_dir, status_file) -> str` | Resolve tracker JSON path |
| `gpu_server_url(args) -> Optional[str]` | Return GPU server URL if backend is `remote` |
| `validation_limits(backend) -> Tuple[int, int]` | Get `(max_tts_bytes, sentence_warn_bytes)` for a backend |

### Step Functions

| Function | Step | Description |
|----------|------|-------------|
| `extract_and_chunk(args, tracker, max_chunk_bytes, reporter)` | 1-4 | Extract text, preprocess, split, and chunk |
| `extract_and_chunk_paged(args, tracker, max_chunk_bytes, reporter)` | 1-4 | Page-aware variant returning `(chunks, page_map)` |
| `validate_and_collect(chunks, tracker, ..., reporter)` | 5 | Validate chunks and filter out already-processed ones |
| `synthesize_chunks(chunks_to_process, total_chunks, tracker, backend, output_dir, ..., reporter, concurrency=1)` | 6 | Run TTS for each chunk and update tracker state |
| `align_chunks(chunks, tracker, args, gpu_server_url, page_map, reporter)` | 7 | Word-level alignment, local or remote |

### PDF Word BBox Extraction

| Function | Description |
|----------|-------------|
| `extract_words_with_bboxes_safe(pdf_path, reporter)` | Extract word bounding boxes from PDFs via PyMuPDF, returning `None` when unavailable so callers can fall back gracefully |

### Status Helpers

| Function | Description |
|----------|-------------|
| `has_failed_chunks(tracker) -> bool` | Check if any chunks failed synthesis or validation |

---

## Synthesis Concurrency

`synthesize_chunks(...)` supports a `concurrency` argument:

- `1` keeps synthesis strictly sequential
- values `> 1` use a `ThreadPoolExecutor`
- tracker writes and reporter events are serialized with a lock

This is especially useful with the `remote` backend:
- the worker submits multiple chunk requests concurrently
- the inference server batcher can then combine compatible `/synthesize` requests into a single GPU call

---

## Internal Calls

```
extract_and_chunk()
├── Extractor.extract_text()
├── Text Processing.preprocess_text()
├── Text Processing.split_into_sentences()
└── Text Processing.create_chunks()

synthesize_chunks()
└── backend.synthesize()  ← TTSBackend protocol

align_chunks()
├── Aligner.align_chunk()                 (local mode)
└── Remote GPU Client.remote_align_chunk()  (remote mode)
```

---

## Dependencies

```
Pipeline Common
├── Pipeline Events      (PipelineReporter)
├── Constants            (chunk patterns, byte limits)
├── Extractor            (text and page extraction)
├── Text Processing      (preprocess, split, chunk, validate)
├── Tracker              (ProcessingTracker, compute_chunk_hash)
├── Aligner              (align_chunk, provider names)
├── TTS Registry         (create_backend_from_args)
├── Remote GPU Client    (remote alignment)
└──▶ consumed by Audio Pipeline
     ├──▶ Highlight Pipeline
     ├──▶ Lipsync Pipeline
     └──▶ Visualization Pipeline (reporter helper only)
```

---

## See Also

- [Pipeline Overview](../../concepts/pipelines.md) — Design overview
- [Pipeline Types](pipeline-types.md) — Request dataclasses
- [Tracker](../core/tracker.md) — State persistence
