"""Lip-sync pipeline runner."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable, List, Optional

from ..concatenator import concatenate
from ..constants import DEFAULT_BG_COLOR, DEFAULT_HIGHLIGHT_COLOR, DEFAULT_TEXT_COLOR, VIDEO_CHUNK_FILE_PATTERN
from .common import (
    align_chunks,
    build_title,
    create_tts_backend,
    extract_and_chunk,
    extract_and_chunk_paged,
    extract_words_with_bboxes_safe,
    get_reporter,
    gpu_server_url,
    has_failed_chunks,
    prepare_tracker,
    synthesize_chunks,
    validation_limits,
    validate_and_collect,
)
from .events import PipelineReporter
from .highlight import parse_resolution
from .types import LipsyncPipelineRequest, PipelineRunResult, coerce_request


BackendFactory = Callable[[object, str], object]


def run_lipsync_pipeline(
    request,
    *,
    reporter: Optional[PipelineReporter] = None,
    backend_factory: Optional[BackendFactory] = None,
) -> PipelineRunResult:
    """Run the lip-sync pipeline."""
    from ..lipsync import get_default_lipsync_provider

    reporter = get_reporter(reporter)
    request = coerce_request(LipsyncPipelineRequest, request)
    factory = backend_factory or create_tts_backend
    fmt = getattr(request, "format", "epub")
    lipsync_provider = getattr(request, "lipsync_provider", get_default_lipsync_provider())

    try:
        backend = factory(request, "lipsync")
    except SystemExit as exc:
        return PipelineRunResult(exit_code=int(exc.code or 1))
    except Exception as exc:
        reporter.line(str(exc))
        return PipelineRunResult(exit_code=1, error_message=str(exc))

    gpu_url = gpu_server_url(request)

    files_to_check = [(request.pdf, "PDF")]
    if getattr(request, "ref_audio", None):
        files_to_check.append((request.ref_audio, "Reference audio"))
    files_to_check.append((request.ref_video, "Reference video"))

    try:
        for path, label in files_to_check:
            if not os.path.isfile(path):
                print(f"Error: {label} not found: {path}", file=sys.stderr)
                return PipelineRunResult(exit_code=1, error_message=f"{label} not found: {path}")

        tracker = prepare_tracker(request)

        page_map = None
        pdf_words = None
        if fmt in ("epub", "reader"):
            chunks, page_map = extract_and_chunk_paged(
                request,
                tracker,
                max_chunk_bytes=backend.max_chunk_bytes,
                reporter=reporter,
            )
        else:
            chunks = extract_and_chunk(
                request,
                tracker,
                max_chunk_bytes=backend.max_chunk_bytes,
                reporter=reporter,
            )
            pdf_words = extract_words_with_bboxes_safe(request.pdf, reporter=reporter)

        max_tts, sent_warn = validation_limits(backend)
        chunks_to_process = validate_and_collect(
            chunks,
            tracker,
            request.verbose,
            max_tts_bytes=max_tts,
            sentence_warn_bytes=sent_warn,
            reporter=reporter,
        )
        synthesize_chunks(
            chunks_to_process,
            len(chunks),
            tracker,
            backend,
            request.output_dir,
            request.verbose,
            reporter=reporter,
            concurrency=getattr(request, "tts_concurrency", 1),
        )
        if has_failed_chunks(tracker):
            msg = "Lipsync pipeline failed: one or more chunks did not complete."
            print(msg, file=sys.stderr)
            return PipelineRunResult(exit_code=1, error_message=msg)

        reporter.phase_start("aligning", "\n=== ALIGNMENT ===")
        aligned_chunks = align_chunks(
            chunks,
            tracker,
            request,
            gpu_server_url=gpu_url,
            page_map=page_map,
            reporter=reporter,
        )

        if not aligned_chunks:
            msg = "No chunks to render."
            print(msg, file=sys.stderr)
            return PipelineRunResult(exit_code=1, error_message=msg)

        reporter.phase_start("lipsync", "\n=== LIP-SYNC GENERATION ===")
        lipsync_clips: List[str] = []
        lipsync_failed = False
        stopped_early = False
        page_times: List[dict] = []
        total_pages = len(aligned_chunks)

        for aligned_chunk in aligned_chunks:
            video_path = os.path.join(
                request.output_dir,
                VIDEO_CHUNK_FILE_PATTERN.format(num=aligned_chunk.chunk_num),
            )
            if tracker.is_video_rendered(aligned_chunk.chunk_num):
                if request.verbose:
                    reporter.line(f"  Chunk {aligned_chunk.chunk_num}: lip-sync already rendered")
                lipsync_clips.append(video_path)
                continue

            # Honour a stop request before committing the GPU to another page.
            if reporter.cancelled():
                stopped_early = True
                reporter.line("  Stop requested — finishing with the pages completed so far.")
                break

            page_num = aligned_chunk.chunk_num
            reporter.line(
                f"  Generating lip-sync for page {page_num}{'  (remote)' if gpu_url else ''}..."
            )
            page_start = time.monotonic()
            reporter.emit(
                phase="lipsync", current=page_num, total=total_pages,
                data={
                    "event": "page_start", "page": page_num,
                    "completed": len(lipsync_clips), "total": total_pages,
                },
            )
            try:
                if gpu_url:
                    from ..remote_gpu import LipsyncCancelled, remote_generate_lipsync

                    try:
                        remote_generate_lipsync(
                            audio_path=aligned_chunk.audio_path,
                            reference_video_path=request.ref_video,
                            output_path=video_path,
                            server_url=gpu_url,
                            provider=lipsync_provider,
                            latentsync_preset=request.latentsync_preset,
                            should_cancel=reporter.should_cancel,
                            on_status=lambda elapsed, p=page_num: reporter.emit(
                                phase="lipsync", current=p, total=total_pages,
                                data={
                                    "event": "page_progress", "page": p,
                                    "elapsed": round(elapsed, 1),
                                    "completed": len(lipsync_clips), "total": total_pages,
                                },
                            ),
                        )
                    except LipsyncCancelled:
                        stopped_early = True
                        reporter.line(f"  Stop requested — page {page_num} aborted.")
                        break
                else:
                    from ..lipsync import generate_lipsync_video

                    kwargs = {
                        "device": request.device,
                        "latentsync_preset": request.latentsync_preset,
                    }
                    if lipsync_provider != "auto":
                        kwargs["provider"] = lipsync_provider
                    generate_lipsync_video(
                        audio_path=aligned_chunk.audio_path,
                        reference_video_path=request.ref_video,
                        output_path=video_path,
                        **kwargs,
                    )
                elapsed = round(time.monotonic() - page_start, 1)
                tracker.mark_video_rendered(aligned_chunk.chunk_num, video_path)
                lipsync_clips.append(video_path)
                page_times.append({"page": page_num, "seconds": elapsed})
                reporter.line(f"  Page {page_num} done in {elapsed:.0f}s.")
                reporter.emit(
                    phase="lipsync", current=page_num, total=total_pages,
                    data={
                        "event": "page_done", "page": page_num, "seconds": elapsed,
                        "completed": len(lipsync_clips), "total": total_pages,
                        "page_times": list(page_times),
                    },
                )
            except Exception as exc:
                reporter.line(f"  Lip-sync error for page {page_num}: {exc}")
                lipsync_failed = True

        if lipsync_failed:
            msg = "Lipsync pipeline failed: one or more video pages did not render."
            print(msg, file=sys.stderr)
            return PipelineRunResult(exit_code=1, error_message=msg)

        if not lipsync_clips:
            msg = (
                "Lip-sync was stopped before any pages were generated."
                if stopped_early
                else "No lip-sync pages were produced."
            )
            print(msg, file=sys.stderr)
            return PipelineRunResult(exit_code=1, error_message=msg)

        # On an early stop, build the output only from the pages that completed;
        # the clips list and aligned_chunks stay index-aligned because the loop
        # appends in order and breaks on cancellation.
        built_chunks = aligned_chunks[: len(lipsync_clips)] if stopped_early else aligned_chunks

        if fmt == "epub":
            result = build_lipsync_epub(
                request, built_chunks, lipsync_clips, tracker, reporter=reporter
            )
        elif fmt == "reader":
            result = build_lipsync_reader(
                request, built_chunks, lipsync_clips, tracker,
                reporter=reporter, stopped_early=stopped_early,
            )
        else:
            result = build_lipsync_mp4(
                request, built_chunks, lipsync_clips, pdf_words=pdf_words, reporter=reporter
            )

        if result.exit_code == 0:
            result.metadata = {
                **(result.metadata or {}),
                "lipsync_stopped_early": stopped_early,
                "lipsync_pages_completed": len(lipsync_clips),
                "lipsync_pages_total": total_pages,
                "lipsync_page_times": page_times,
            }
        return result
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return PipelineRunResult(exit_code=1, error_message=str(exc))


def build_lipsync_epub(
    request: LipsyncPipelineRequest,
    aligned_chunks,
    lipsync_clips,
    tracker,
    *,
    reporter: Optional[PipelineReporter] = None,
) -> PipelineRunResult:
    """Assemble an EPUB3 output with lip-synced video."""
    from ..epub_builder import EPUBBuilder

    reporter = get_reporter(reporter)
    output_name = request.output or (Path(request.pdf).stem + "_lipsync.epub")
    request.output = output_name

    if tracker.is_epub_built() and not request.clean:
        dest = os.path.join(request.output_dir, output_name)
        reporter.line(f"\nEPUB already built: {dest}")
        return PipelineRunResult(exit_code=0, output_name=output_name, output_path=dest)

    reporter.phase_start("building", "\n=== BUILDING EPUB ===")
    builder = EPUBBuilder(title=build_title(request.pdf), language=request.language)

    clip_map = {}
    for aligned_chunk, clip in zip(aligned_chunks, lipsync_clips):
        clip_map[aligned_chunk.chunk_num] = clip

    page_chunks: dict[int, list] = defaultdict(list)
    for aligned_chunk in aligned_chunks:
        page = aligned_chunk.pages[0] if aligned_chunk.pages else 1
        page_chunks[page].append(aligned_chunk)

    for page_num in sorted(page_chunks):
        chunks_on_page = page_chunks[page_num]
        page_clip_paths = [
            clip_map[aligned_chunk.chunk_num]
            for aligned_chunk in chunks_on_page
            if aligned_chunk.chunk_num in clip_map
        ]

        video_path = None
        if len(page_clip_paths) == 1:
            video_path = page_clip_paths[0]
        elif len(page_clip_paths) > 1:
            concat_path = os.path.join(request.output_dir, f"face_page_{page_num:03d}.mp4")
            try:
                concatenate(request.output_dir, concat_path, ext="mp4", files=page_clip_paths)
                video_path = concat_path
            except Exception as exc:
                reporter.line(f"  Warning: could not concat lipsync videos for page {page_num}: {exc}")
                video_path = page_clip_paths[0]

        builder.add_chapter(page_num, chunks_on_page, lipsync_video_path=video_path)

    dest = os.path.join(request.output_dir, output_name)
    builder.build(dest)
    tracker.mark_epub_built()
    reporter.line(f"\nDone: {dest}")
    return PipelineRunResult(exit_code=0, output_name=output_name, output_path=dest)


def build_lipsync_mp4(
    request: LipsyncPipelineRequest,
    aligned_chunks,
    lipsync_clips,
    *,
    pdf_words=None,
    reporter: Optional[PipelineReporter] = None,
) -> PipelineRunResult:
    """Compose the final MP4 output."""
    from ..video_composer import compose_lipsync_video

    reporter = get_reporter(reporter)
    output_name = request.output or (Path(request.pdf).stem + "_lipsync.mp4")
    request.output = output_name
    width, height = parse_resolution(request.resolution)

    if pdf_words:
        from ..page_renderer import PageRenderer
        from ..word_matcher import match_words_to_bboxes

        reporter.phase_start("matching", "\n=== MATCHING WORDS TO PAGE POSITIONS ===")
        match_words_to_bboxes(aligned_chunks, pdf_words)

        reporter.phase_start("composing", "\n=== COMPOSING FINAL VIDEO (page images) ===")
        renderer = PageRenderer(
            pdf_path=request.pdf,
            width=width,
            height=height,
        )
    else:
        from ..highlight_renderer import HighlightRenderer

        reporter.phase_start("composing", "\n=== COMPOSING FINAL VIDEO ===")
        renderer = HighlightRenderer(
            width=width,
            height=height,
            font_size=request.font_size,
            highlight_color=DEFAULT_HIGHLIGHT_COLOR,
            text_color=DEFAULT_TEXT_COLOR,
            bg_color=DEFAULT_BG_COLOR,
        )

    dest = os.path.join(request.output_dir, output_name)
    compose_lipsync_video(
        aligned_chunks=aligned_chunks,
        lipsync_clips=lipsync_clips,
        renderer=renderer,
        output_path=dest,
        fps=request.fps,
        face_position=request.face_position,
        face_scale=request.face_scale,
    )
    reporter.line(f"\nDone: {dest}")
    return PipelineRunResult(exit_code=0, output_name=output_name, output_path=dest)


def _normalize_presenter_chunk(src: str, dest: str, duration: float, fps: int) -> None:
    """Re-encode *src* to a uniform fps/codec, trimmed to *duration* seconds.

    Re-encoding (rather than a stream copy) is required so the concatenated
    presenter video has frame-accurate chunk boundaries that line up with the
    reader manifest's global word offsets.
    """
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", src,
            "-t", f"{duration:.3f}",
            "-r", str(fps),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100",
            "-movflags", "+faststart",
            dest,
        ],
        capture_output=True,
        check=True,
    )


def _concat_presenter_chunks(files: List[str], dest: str) -> None:
    """Concatenate uniformly-encoded presenter chunks via the ffmpeg demuxer."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as fh:
        for path in files:
            fh.write(f"file '{os.path.abspath(path)}'\n")
        list_path = fh.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", dest],
            capture_output=True,
            check=True,
        )
    finally:
        os.unlink(list_path)


def _build_presenter_video(
    aligned_chunks,
    lipsync_clips,
    output_dir: str,
    fps: int,
) -> str:
    """Concatenate the per-chunk lip-sync clips into a single presenter video.

    Each clip is normalised to its exact chunk-audio duration first so the
    presenter timeline matches the reader manifest. The presenter video keeps
    its own audio track, so the viewer can use it as the sole media element.
    """
    from ..reader_assets import PRESENTER_NAME
    from ..lipsync import _get_audio_duration

    dest = os.path.join(output_dir, PRESENTER_NAME)
    tmpdir = tempfile.mkdtemp(prefix="presenter_", dir=output_dir)
    try:
        normalized: List[str] = []
        for aligned_chunk, clip in zip(aligned_chunks, lipsync_clips):
            duration = _get_audio_duration(aligned_chunk.audio_path)
            norm = os.path.join(tmpdir, f"chunk_{aligned_chunk.chunk_num:03d}.mp4")
            _normalize_presenter_chunk(clip, norm, duration, fps)
            normalized.append(norm)
        _concat_presenter_chunks(normalized, dest)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)
    return dest


def build_lipsync_reader(
    request: LipsyncPipelineRequest,
    aligned_chunks,
    lipsync_clips,
    tracker,
    *,
    reporter: Optional[PipelineReporter] = None,
    stopped_early: bool = False,
) -> PipelineRunResult:
    """Build the reader bundle: manifest + audio + page images + presenter video.

    This is the default web output — the presenter video and the document are
    delivered separately so the browser viewer can combine them flexibly.
    """
    from ..reader_assets import MANIFEST_NAME, PRESENTER_NAME, build_reader_assets

    reporter = get_reporter(reporter)

    reporter.phase_start("presenter", "\n=== BUILDING PRESENTER VIDEO ===")
    presenter_path = os.path.join(request.output_dir, PRESENTER_NAME)
    # A cached presenter covers every page; rebuild it when an early stop means
    # the output should only span the pages that actually completed.
    if (
        tracker.is_presenter_built()
        and os.path.isfile(presenter_path)
        and not request.clean
        and not stopped_early
    ):
        reporter.line(f"  Presenter video already built: {presenter_path}")
    else:
        presenter_path = _build_presenter_video(
            aligned_chunks, lipsync_clips, request.output_dir, request.fps,
        )
        tracker.mark_presenter_built()
        reporter.line(f"  Presenter video: {presenter_path}")

    reporter.phase_start("reader_assets", "\n=== BUILDING READER ASSETS ===")
    manifest_path = build_reader_assets(
        aligned_chunks=aligned_chunks,
        output_dir=request.output_dir,
        pdf_path=request.pdf,
        title=build_title(request.pdf),
        language=request.language,
        presenter=PRESENTER_NAME,
    )
    if not manifest_path:
        msg = "Reader bundle could not be built: no chunks available."
        print(msg, file=sys.stderr)
        return PipelineRunResult(exit_code=1, error_message=msg)

    _warn_on_presenter_drift(presenter_path, manifest_path, reporter)

    request.output = MANIFEST_NAME
    reporter.line(f"\nDone: {manifest_path}")
    return PipelineRunResult(exit_code=0, output_name=MANIFEST_NAME, output_path=manifest_path)


def _warn_on_presenter_drift(presenter_path: str, manifest_path: str, reporter) -> None:
    """Log a warning if the presenter video and manifest timelines diverge."""
    import json

    from ..lipsync import _get_audio_duration

    try:
        presenter_dur = _get_audio_duration(presenter_path)
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest_dur = json.load(fh).get("duration", 0.0)
    except Exception:  # noqa: BLE001
        return
    drift = abs(presenter_dur - manifest_dur)
    if drift > 0.05:
        reporter.line(
            f"  Warning: presenter video ({presenter_dur:.3f}s) and reader "
            f"timeline ({manifest_dur:.3f}s) differ by {drift:.3f}s."
        )
