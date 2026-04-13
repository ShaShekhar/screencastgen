"""Lip-sync pipeline runner."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

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
        if fmt == "epub":
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
        lipsync_clips = []
        lipsync_failed = False
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

            reporter.line(
                f"  Generating lip-sync for chunk {aligned_chunk.chunk_num}{'  (remote)' if gpu_url else ''}..."
            )
            reporter.emit(phase="lipsync", current=aligned_chunk.chunk_num, total=len(aligned_chunks))
            try:
                if gpu_url:
                    from ..remote_gpu import remote_generate_lipsync

                    remote_generate_lipsync(
                        audio_path=aligned_chunk.audio_path,
                        reference_video_path=request.ref_video,
                        output_path=video_path,
                        server_url=gpu_url,
                        provider=lipsync_provider,
                        latentsync_preset=request.latentsync_preset,
                    )
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
                tracker.mark_video_rendered(aligned_chunk.chunk_num, video_path)
                lipsync_clips.append(video_path)
            except Exception as exc:
                reporter.line(f"  Lip-sync error for chunk {aligned_chunk.chunk_num}: {exc}")
                lipsync_failed = True

        if lipsync_failed:
            msg = "Lipsync pipeline failed: one or more video chunks did not render."
            print(msg, file=sys.stderr)
            return PipelineRunResult(exit_code=1, error_message=msg)

        if fmt == "epub":
            return build_lipsync_epub(request, aligned_chunks, lipsync_clips, tracker, reporter=reporter)
        return build_lipsync_mp4(request, aligned_chunks, lipsync_clips, pdf_words=pdf_words, reporter=reporter)
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
