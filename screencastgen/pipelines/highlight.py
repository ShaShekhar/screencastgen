"""Highlight pipeline runner."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

from ..constants import DEFAULT_BG_COLOR, DEFAULT_HIGHLIGHT_COLOR, DEFAULT_TEXT_COLOR
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
from .types import HighlightPipelineRequest, PipelineRunResult, coerce_request


BackendFactory = Callable[[object, str], object]


def parse_resolution(res_str: str) -> tuple[int, int]:
    """Parse a WxH resolution string."""
    parts = res_str.lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"Invalid resolution: {res_str}. Use WxH format (e.g. 1280x720)")
    return int(parts[0]), int(parts[1])


def run_highlight_pipeline(
    request,
    *,
    reporter: Optional[PipelineReporter] = None,
    backend_factory: Optional[BackendFactory] = None,
) -> PipelineRunResult:
    """Run the highlighted-text pipeline."""
    reporter = get_reporter(reporter)
    request = coerce_request(HighlightPipelineRequest, request)
    factory = backend_factory or create_tts_backend
    fmt = getattr(request, "format", "epub")

    try:
        backend = factory(request, "highlight")
    except SystemExit as exc:
        return PipelineRunResult(exit_code=int(exc.code or 1))
    except Exception as exc:
        reporter.line(str(exc))
        return PipelineRunResult(exit_code=1, error_message=str(exc))

    try:
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
        )
        if has_failed_chunks(tracker):
            msg = "Highlight pipeline failed: one or more chunks did not complete."
            print(msg, file=sys.stderr)
            return PipelineRunResult(exit_code=1, error_message=msg)

        reporter.phase_start("aligning", "\n=== ALIGNMENT ===")
        aligned_chunks = align_chunks(
            chunks,
            tracker,
            request,
            gpu_server_url=gpu_server_url(request),
            page_map=page_map,
            reporter=reporter,
        )

        if not aligned_chunks:
            msg = "No chunks to render."
            print(msg, file=sys.stderr)
            return PipelineRunResult(exit_code=1, error_message=msg)

        if fmt == "epub":
            return build_highlight_epub(request, aligned_chunks, tracker, reporter=reporter)
        return build_highlight_mp4(request, aligned_chunks, pdf_words=pdf_words, reporter=reporter)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return PipelineRunResult(exit_code=1, error_message=str(exc))


def build_highlight_epub(
    request: HighlightPipelineRequest,
    aligned_chunks,
    tracker,
    *,
    reporter: Optional[PipelineReporter] = None,
) -> PipelineRunResult:
    """Assemble an EPUB3 highlighted-text output."""
    from ..epub_builder import EPUBBuilder

    reporter = get_reporter(reporter)
    output_name = request.output or (Path(request.pdf).stem + "_highlight.epub")
    request.output = output_name

    if tracker.is_epub_built() and not request.clean:
        dest = os.path.join(request.output_dir, output_name)
        reporter.line(f"\nEPUB already built: {dest}")
        return PipelineRunResult(exit_code=0, output_name=output_name, output_path=dest)

    reporter.phase_start("building", "\n=== BUILDING EPUB ===")
    builder = EPUBBuilder(title=build_title(request.pdf), language=request.language)

    page_chunks: dict[int, list] = defaultdict(list)
    for aligned_chunk in aligned_chunks:
        page = aligned_chunk.pages[0] if aligned_chunk.pages else 1
        page_chunks[page].append(aligned_chunk)

    for page_num in sorted(page_chunks):
        builder.add_chapter(page_num, page_chunks[page_num])

    dest = os.path.join(request.output_dir, output_name)
    builder.build(dest)
    tracker.mark_epub_built()
    reporter.line(f"\nDone: {dest}")
    return PipelineRunResult(exit_code=0, output_name=output_name, output_path=dest)


def build_highlight_mp4(
    request: HighlightPipelineRequest,
    aligned_chunks,
    *,
    pdf_words=None,
    reporter: Optional[PipelineReporter] = None,
) -> PipelineRunResult:
    """Render the MP4 highlighted-text output."""
    from ..video_composer import compose_highlight_video

    reporter = get_reporter(reporter)
    output_name = request.output or (Path(request.pdf).stem + "_highlight.mp4")
    request.output = output_name
    width, height = parse_resolution(request.resolution)

    # Use PageRenderer for PDF inputs when word bboxes are available
    if pdf_words:
        from ..page_renderer import PageRenderer
        from ..word_matcher import match_words_to_bboxes

        reporter.phase_start("matching", "\n=== MATCHING WORDS TO PAGE POSITIONS ===")
        match_words_to_bboxes(aligned_chunks, pdf_words)

        reporter.phase_start("rendering", "\n=== RENDERING VIDEO (page images) ===")
        renderer = PageRenderer(
            pdf_path=request.pdf,
            width=width,
            height=height,
        )
    else:
        from ..highlight_renderer import HighlightRenderer

        reporter.phase_start("rendering", "\n=== RENDERING VIDEO ===")
        renderer = HighlightRenderer(
            width=width,
            height=height,
            font_size=request.font_size,
            highlight_color=DEFAULT_HIGHLIGHT_COLOR,
            text_color=DEFAULT_TEXT_COLOR,
            bg_color=DEFAULT_BG_COLOR,
        )

    dest = os.path.join(request.output_dir, output_name)
    compose_highlight_video(
        aligned_chunks=aligned_chunks,
        renderer=renderer,
        output_path=dest,
        fps=request.fps,
    )
    reporter.line(f"\nDone: {dest}")
    return PipelineRunResult(exit_code=0, output_name=output_name, output_path=dest)
