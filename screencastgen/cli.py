"""Command-line interface for screencastgen."""

import argparse
import os
import re
import sys
from pathlib import Path

from . import __version__
from .concatenator import concatenate
from .constants import (
    CHUNK_FILE_PATTERN,
    DEFAULT_BG_COLOR,
    DEFAULT_FONT_SIZE,
    DEFAULT_HIGHLIGHT_COLOR,
    DEFAULT_LANGUAGE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_STATUS_FILE,
    DEFAULT_TEXT_COLOR,
    DEFAULT_VIDEO_FPS,
    DEFAULT_VIDEO_HEIGHT,
    DEFAULT_VIDEO_WIDTH,
    MAX_CHUNK_BYTES,
    VIDEO_CHUNK_FILE_PATTERN,
)
from .extractor import extract_text, extract_text_by_page
from .text_processing import (
    create_chunks,
    create_chunks_with_pages,
    preprocess_text,
    split_into_sentences,
    split_into_sentences_by_page,
    validate_chunk,
)
from .tracker import ProcessingTracker, compute_chunk_hash


def _add_common_args(p: argparse.ArgumentParser) -> None:
    """Add arguments shared by all subcommands."""
    p.add_argument("pdf", help="Path to the input PDF file")
    p.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for chunk files (default: {DEFAULT_OUTPUT_DIR})",
    )
    p.add_argument(
        "--language",
        default=DEFAULT_LANGUAGE,
        help=f"Language code (default: {DEFAULT_LANGUAGE})",
    )
    p.add_argument(
        "--status-file",
        default=DEFAULT_STATUS_FILE,
        help=f"Resume-state JSON file (default: {DEFAULT_STATUS_FILE})",
    )
    p.add_argument("--clean", action="store_true", help="Ignore previous state and start fresh")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose output")


def _add_tts_backend_args(p: argparse.ArgumentParser) -> None:
    """Add arguments for TTS backend selection."""
    from .backends import (
        get_backend_names,
        get_default_backend_name,
        register_backend_args,
    )

    p.add_argument(
        "--backend",
        default=get_default_backend_name(context="cli"),
        choices=get_backend_names(context="cli"),
        help="TTS backend",
    )
    p.add_argument("--device", default="auto", help="Device for local models: auto, cpu, or cuda (default: auto)")
    p.add_argument("--voice", default=None, help="Voice name (backend-specific)")
    # Common backend options
    p.add_argument("--ref-audio", default=None, help="Reference audio for voice cloning backends")
    p.add_argument("--ref-text", default=None, help="Transcript of reference audio")
    register_backend_args(p, context="cli")


def _add_video_args(p: argparse.ArgumentParser) -> None:
    """Add arguments for video output subcommands."""
    p.add_argument("--font-size", type=int, default=DEFAULT_FONT_SIZE, help=f"Font size (default: {DEFAULT_FONT_SIZE})")
    p.add_argument(
        "--resolution",
        default=f"{DEFAULT_VIDEO_WIDTH}x{DEFAULT_VIDEO_HEIGHT}",
        help=f"Video resolution WxH (default: {DEFAULT_VIDEO_WIDTH}x{DEFAULT_VIDEO_HEIGHT})",
    )
    p.add_argument("--fps", type=int, default=DEFAULT_VIDEO_FPS, help=f"Frame rate (default: {DEFAULT_VIDEO_FPS})")


def _add_provider_args(p: argparse.ArgumentParser, *, include_lipsync: bool = False) -> None:
    """Add alignment and lip-sync provider selection args."""
    from .aligner import (
        get_alignment_provider_names,
        get_default_alignment_provider,
    )

    p.add_argument(
        "--aligner",
        default=get_default_alignment_provider(),
        choices=get_alignment_provider_names(),
        help="Alignment provider",
    )

    if include_lipsync:
        from .lipsync import (
            get_lipsync_provider_names,
            get_default_lipsync_provider,
        )

        p.add_argument(
            "--lipsync-provider",
            default=get_default_lipsync_provider(),
            choices=get_lipsync_provider_names(),
            help="Lip-sync provider",
        )


def _parse_resolution(res_str: str) -> tuple:
    parts = res_str.lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"Invalid resolution: {res_str}. Use WxH format (e.g. 1280x720)")
    return int(parts[0]), int(parts[1])


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="screencastgen",
        description="Convert PDF documents to audio and video.",
    )
    p.add_argument(
        "-V", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    sub = p.add_subparsers(dest="command")

    # --- audio (default) ---
    audio_p = sub.add_parser("audio", help="Convert PDF to audio (default)")
    _add_common_args(audio_p)
    _add_tts_backend_args(audio_p)
    audio_p.add_argument("-o", "--output", help="Output audio filename (default: <pdf-stem>.<ext>)")
    audio_p.add_argument("--no-concat", action="store_true", help="Skip final concatenation step")

    # --- highlight ---
    hl_p = sub.add_parser("highlight", help="Create highlighted-text video from PDF")
    _add_common_args(hl_p)
    _add_tts_backend_args(hl_p)
    _add_provider_args(hl_p)
    _add_video_args(hl_p)
    hl_p.add_argument("-o", "--output", help="Output filename (default: <pdf-stem>_highlight.epub)")
    hl_p.add_argument(
        "--format", default="epub", choices=["epub", "mp4"],
        help="Output format (default: epub)",
    )

    # --- lipsync ---
    ls_p = sub.add_parser("lipsync", help="Create lip-synced video with voice cloning")
    _add_common_args(ls_p)
    _add_tts_backend_args(ls_p)
    _add_provider_args(ls_p, include_lipsync=True)
    _add_video_args(ls_p)
    ls_p.add_argument("-o", "--output", help="Output filename (default: <pdf-stem>_lipsync.epub)")
    ls_p.add_argument("--ref-video", required=True, help="Reference face video clip (~10s)")
    ls_p.add_argument(
        "--format", default="epub", choices=["epub", "mp4"],
        help="Output format (default: epub)",
    )
    ls_p.add_argument(
        "--face-position", default="left", choices=["left", "right", "center"],
        help="Position of the face in the video (default: left)",
    )

    # --- download-models ---
    from .models import register_model_download_args

    dm_p = sub.add_parser("download-models", help="Pre-download ML model weights")
    register_model_download_args(dm_p)

    return p


# ---------------------------------------------------------------------------
# Backend factory
# ---------------------------------------------------------------------------

def _create_tts_backend(args, invocation: str):
    """Build the appropriate TTSBackend from parsed CLI args."""
    from .backends import create_backend_from_args

    try:
        return create_backend_from_args(args, invocation=invocation)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Shared pipeline steps
# ---------------------------------------------------------------------------

def _extract_and_chunk(args, tracker, max_chunk_bytes=MAX_CHUNK_BYTES):
    """Steps 1-4: Extract, preprocess, split, chunk."""
    pdf_path = args.pdf
    if not os.path.isfile(pdf_path):
        print(f"Error: {pdf_path} not found", file=sys.stderr)
        sys.exit(1)

    if tracker.status["total_chunks"] > 0 and not args.clean:
        summary = tracker.get_summary()
        print("=== RESUMING PREVIOUS SESSION ===")
        print(f"Total chunks: {summary['total']}")
        print(f"Already processed: {summary['processed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Remaining: {summary['remaining']}")

    print("\nStep 1: Extracting text from PDF...")
    raw_text = extract_text(pdf_path)

    print("Step 2: Preprocessing text...")
    processed = preprocess_text(raw_text)

    print("Step 3: Splitting into sentences...")
    sentences = split_into_sentences(processed)

    print("Step 4: Creating chunks...")
    chunks = create_chunks(sentences, max_bytes=max_chunk_bytes)
    print(f"Created {len(chunks)} chunks")

    tracker.status["total_chunks"] = len(chunks)
    tracker.save()

    return chunks


def _extract_and_chunk_paged(args, tracker, max_chunk_bytes=MAX_CHUNK_BYTES):
    """Page-aware extraction and chunking for EPUB output.

    Returns ``(chunks, page_map)`` where *chunks* is a flat list of chunk
    texts (compatible with the rest of the pipeline) and *page_map* is a
    ``{chunk_num: [page_numbers]}`` dict.
    """
    pdf_path = args.pdf
    if not os.path.isfile(pdf_path):
        print(f"Error: {pdf_path} not found", file=sys.stderr)
        sys.exit(1)

    if tracker.status["total_chunks"] > 0 and not args.clean:
        summary = tracker.get_summary()
        print("=== RESUMING PREVIOUS SESSION ===")
        print(f"Total chunks: {summary['total']}")
        print(f"Already processed: {summary['processed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Remaining: {summary['remaining']}")

    print("\nStep 1: Extracting text from PDF (page-aware)...")
    pages = extract_text_by_page(pdf_path)

    print("Step 2-3: Preprocessing and splitting per page...")
    page_sentences = split_into_sentences_by_page(pages)

    print("Step 4: Creating chunks (preserving page info)...")
    chunks_with_pages = create_chunks_with_pages(page_sentences, max_bytes=max_chunk_bytes)

    chunks = [text for text, _pages in chunks_with_pages]
    page_map = {i + 1: pg for i, (_, pg) in enumerate(chunks_with_pages)}

    print(f"Created {len(chunks)} chunks across {len(pages)} pages")

    tracker.status["total_chunks"] = len(chunks)
    tracker.save()

    return chunks, page_map


def _validate_and_collect(chunks, tracker, verbose=False, max_tts_bytes=None, sentence_warn_bytes=None):
    """Step 5: Validate chunks, return list of (chunk_num, chunk, chunk_hash) to process."""
    print("\nStep 5: Validating chunks...")

    validate_kwargs = {}
    if max_tts_bytes is not None:
        validate_kwargs["max_tts_bytes"] = max_tts_bytes
    if sentence_warn_bytes is not None:
        validate_kwargs["sentence_warn_bytes"] = sentence_warn_bytes

    chunks_to_process = []
    for i, chunk in enumerate(chunks):
        chunk_num = i + 1
        chunk_hash = compute_chunk_hash(chunk)

        if tracker.is_processed(chunk_num, chunk_hash):
            if verbose:
                print(f"  Chunk {chunk_num}: already processed")
            continue

        is_valid, issues = validate_chunk(chunk, chunk_num, **validate_kwargs)
        if is_valid:
            chunks_to_process.append((chunk_num, chunk, chunk_hash))
        else:
            print(f"\n  Chunk {chunk_num} FAILED validation:")
            for issue in issues:
                print(f"    - {issue}")
            tracker.mark_failed(chunk_num, chunk_hash, "; ".join(issues))

    print(f"\nChunks to process: {len(chunks_to_process)}")
    return chunks_to_process


def _synthesize_chunks(chunks_to_process, total_chunks, tracker, backend, output_dir, verbose=False):
    """Synthesize audio chunks using any TTSBackend. Returns count processed."""
    if not chunks_to_process:
        summary = tracker.get_summary()
        print("\nAll chunks already processed or failed validation.")
        print(f"  Total: {summary['total']}  Processed: {summary['processed']}  Failed: {summary['failed']}")
        return 0

    ext = backend.output_format
    processed_count = 0
    for chunk_num, chunk, chunk_hash in chunks_to_process:
        chunk_file = os.path.join(output_dir, CHUNK_FILE_PATTERN.format(num=chunk_num, ext=ext))
        print(f"\nProcessing chunk {chunk_num}/{total_chunks}...")
        if verbose:
            print(f"  Size: {len(chunk.encode('utf-8'))} bytes")
            print(f"  Preview: {chunk[:80]}...")

        try:
            backend.synthesize(chunk, chunk_file)
            tracker.mark_processed(chunk_num, chunk_hash, chunk_file)
            processed_count += 1
            print(f"  Created {chunk_file}")
        except Exception as exc:
            error_msg = str(exc)
            print(f"  Error: {error_msg}")
            tracker.mark_failed(chunk_num, chunk_hash, error_msg)

            if "sentence" in error_msg.lower() and "too long" in error_msg.lower():
                for j, sent in enumerate(re.split(r"(?<=[.!?])\s*", chunk)):
                    if sent.strip() and len(sent.encode("utf-8")) > 850:
                        print(f"    Sentence {j + 1}: {len(sent.encode('utf-8'))} bytes")

    summary = tracker.get_summary()
    print(f"\n=== SYNTHESIS COMPLETE ===")
    print(f"Processed this session: {processed_count}")
    print(f"Total processed: {summary['processed']}/{summary['total']}")
    print(f"Failed: {summary['failed']}")

    if summary["failed"] > 0:
        print("\nFailed chunks:")
        for cnum, details in tracker.status["failed_chunks"].items():
            print(f"  Chunk {cnum}: {details['error']}")
        print("Re-run the command to retry failed chunks.")

    return processed_count


def _has_failed_chunks(tracker) -> bool:
    """Return True when any chunk failed validation or synthesis."""
    return tracker.get_summary()["failed"] > 0


def _align_chunks(chunks, tracker, args, gpu_server_url=None, page_map=None):
    """Run alignment on all processed chunks. Returns list of AlignedChunk.

    When *gpu_server_url* is set, alignment is offloaded to the GPU server.
    *page_map*, if provided, is ``{chunk_num: [page_numbers]}``.
    """
    from .types import AlignedChunk, WordTiming

    from .aligner import get_default_alignment_provider

    use_remote = gpu_server_url is not None
    aligner_name = getattr(args, "aligner", get_default_alignment_provider())

    aligned_chunks = []
    for i, chunk in enumerate(chunks):
        chunk_num = i + 1
        chunk_hash = compute_chunk_hash(chunk)
        if not tracker.is_processed(chunk_num, chunk_hash):
            continue

        audio_path = tracker.status["processed_chunks"][str(chunk_num)]["output_file"]

        if tracker.is_aligned(chunk_num):
            if args.verbose:
                print(f"  Chunk {chunk_num}: already aligned")
            words_data = tracker.get_alignment(chunk_num)
            words = [WordTiming(w["word"], w["start"], w["end"]) for w in words_data]
        else:
            print(f"  Aligning chunk {chunk_num}{'  (remote)' if use_remote else ''}...")
            try:
                if use_remote:
                    from .remote_gpu import remote_align_chunk
                    words = remote_align_chunk(
                        audio_path, chunk,
                        server_url=gpu_server_url,
                        language=args.language,
                        provider=aligner_name,
                    )
                else:
                    from .aligner import align_chunk
                    words = align_chunk(
                        audio_path,
                        chunk,
                        provider=aligner_name,
                        language=args.language,
                        device=getattr(args, "device", "auto"),
                    )
                tracker.mark_aligned(chunk_num, words)
            except Exception as exc:
                print(f"  Alignment error for chunk {chunk_num}: {exc}")
                words = []

        pages = page_map.get(chunk_num, []) if page_map else []
        aligned_chunks.append(AlignedChunk(
            chunk_num=chunk_num, text=chunk, audio_path=audio_path,
            words=words, pages=pages,
        ))

    return aligned_chunks


# ---------------------------------------------------------------------------
# Remote GPU helpers
# ---------------------------------------------------------------------------

def _gpu_server_url(args):
    """Return the GPU server URL if the backend is remote, else None."""
    if getattr(args, "backend", None) == "remote":
        return getattr(args, "tts_server_url", "http://localhost:8100")
    return None


# ---------------------------------------------------------------------------
# Backend-aware validation limits
# ---------------------------------------------------------------------------

def _validation_limits(backend):
    """Return (max_tts_bytes, sentence_warn_bytes) appropriate for *backend*."""
    from .constants import SENTENCE_WARN_BYTES, MAX_TTS_BYTES

    max_tts = backend.max_chunk_bytes
    # For local backends with large chunk limits, sentence-level checks are
    # irrelevant — use a very high threshold to effectively disable them.
    if max_tts > MAX_TTS_BYTES:
        return max_tts, max_tts
    return MAX_TTS_BYTES, SENTENCE_WARN_BYTES


# ---------------------------------------------------------------------------
# Subcommand runners
# ---------------------------------------------------------------------------

def run_audio_pipeline(args) -> int:
    """Audio-only pipeline — works with any TTS backend."""
    backend = _create_tts_backend(args, invocation="audio")
    ext = backend.output_format
    output_file = args.output or (Path(args.pdf).stem + f".{ext}")
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    status_path = os.path.join(output_dir, args.status_file)
    if args.clean and os.path.exists(status_path):
        os.remove(status_path)

    tracker = ProcessingTracker(status_path)
    chunks = _extract_and_chunk(args, tracker, max_chunk_bytes=backend.max_chunk_bytes)
    max_tts, sent_warn = _validation_limits(backend)
    chunks_to_process = _validate_and_collect(
        chunks, tracker, args.verbose,
        max_tts_bytes=max_tts, sentence_warn_bytes=sent_warn,
    )
    _synthesize_chunks(chunks_to_process, len(chunks), tracker, backend, output_dir, args.verbose)
    if _has_failed_chunks(tracker):
        print("Audio pipeline failed: one or more chunks did not complete.", file=sys.stderr)
        return 1

    if not args.no_concat:
        summary = tracker.get_summary()
        if summary["processed"] > 0:
            dest = os.path.join(output_dir, output_file)
            print(f"\nConcatenating into {dest}...")
            try:
                concatenate(output_dir, dest, ext=ext)
                print(f"Done: {dest}")
            except FileNotFoundError as exc:
                print(f"Skipping concatenation: {exc}")
                return 1
            except Exception as exc:
                print(f"Concatenation failed: {exc}")
                return 1
            if not os.path.isfile(dest):
                print(f"Concatenation failed: output file missing at {dest}", file=sys.stderr)
                return 1
        else:
            print("Audio pipeline failed: no synthesized chunks were produced.", file=sys.stderr)
            return 1

    return 0


def run_highlight_pipeline(args) -> int:
    """Highlighted-text pipeline — EPUB3 (default) or MP4 video."""
    fmt = getattr(args, "format", "epub")

    backend = _create_tts_backend(args, invocation="highlight")
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    status_path = os.path.join(output_dir, args.status_file)
    if args.clean and os.path.exists(status_path):
        os.remove(status_path)

    tracker = ProcessingTracker(status_path)

    # -- extraction & chunking (page-aware for EPUB) --
    page_map = None
    if fmt == "epub":
        chunks, page_map = _extract_and_chunk_paged(
            args, tracker, max_chunk_bytes=backend.max_chunk_bytes,
        )
    else:
        chunks = _extract_and_chunk(args, tracker, max_chunk_bytes=backend.max_chunk_bytes)

    max_tts, sent_warn = _validation_limits(backend)
    chunks_to_process = _validate_and_collect(
        chunks, tracker, args.verbose,
        max_tts_bytes=max_tts, sentence_warn_bytes=sent_warn,
    )
    _synthesize_chunks(chunks_to_process, len(chunks), tracker, backend, output_dir, args.verbose)
    if _has_failed_chunks(tracker):
        print("Highlight pipeline failed: one or more chunks did not complete.", file=sys.stderr)
        return 1

    # -- alignment --
    print("\n=== ALIGNMENT ===")
    aligned_chunks = _align_chunks(
        chunks, tracker, args,
        gpu_server_url=_gpu_server_url(args),
        page_map=page_map,
    )

    if not aligned_chunks:
        print("No chunks to render.", file=sys.stderr)
        return 1

    if fmt == "epub":
        return _build_highlight_epub(args, aligned_chunks, tracker, output_dir)
    else:
        return _build_highlight_mp4(args, aligned_chunks, output_dir)


def _build_highlight_epub(args, aligned_chunks, tracker, output_dir) -> int:
    """Assemble EPUB3 with Media Overlays from aligned chunks."""
    from .epub_builder import EPUBBuilder

    output_file = args.output or (Path(args.pdf).stem + "_highlight.epub")

    if tracker.is_epub_built() and not args.clean:
        dest = os.path.join(output_dir, output_file)
        print(f"\nEPUB already built: {dest}")
        return 0

    print("\n=== BUILDING EPUB ===")
    title = Path(args.pdf).stem.replace("_", " ").replace("-", " ").title()
    builder = EPUBBuilder(title=title, language=args.language)

    # Group chunks by their first page
    from collections import defaultdict
    page_chunks: dict = defaultdict(list)
    for ac in aligned_chunks:
        page = ac.pages[0] if ac.pages else 1
        page_chunks[page].append(ac)

    for page_num in sorted(page_chunks):
        builder.add_chapter(page_num, page_chunks[page_num])

    dest = os.path.join(output_dir, output_file)
    builder.build(dest)
    tracker.mark_epub_built()
    print(f"\nDone: {dest}")
    return 0


def _build_highlight_mp4(args, aligned_chunks, output_dir) -> int:
    """Render MP4 video with word-highlighted text (legacy path)."""
    from .highlight_renderer import HighlightRenderer
    from .video_composer import compose_highlight_video

    output_file = args.output or (Path(args.pdf).stem + "_highlight.mp4")
    width, height = _parse_resolution(args.resolution)

    print("\n=== RENDERING VIDEO ===")
    renderer = HighlightRenderer(
        width=width, height=height, font_size=args.font_size,
        highlight_color=DEFAULT_HIGHLIGHT_COLOR,
        text_color=DEFAULT_TEXT_COLOR,
        bg_color=DEFAULT_BG_COLOR,
    )

    dest = os.path.join(output_dir, output_file)
    compose_highlight_video(
        aligned_chunks=aligned_chunks, renderer=renderer,
        output_path=dest, fps=args.fps,
    )
    print(f"\nDone: {dest}")
    return 0


def run_lipsync_pipeline(args) -> int:
    """Lip-synced pipeline — EPUB3 (default) or MP4 video."""
    fmt = getattr(args, "format", "epub")
    ref_audio = getattr(args, "ref_audio", None)
    from .lipsync import get_default_lipsync_provider

    lipsync_provider = getattr(args, "lipsync_provider", get_default_lipsync_provider())
    backend = _create_tts_backend(args, invocation="lipsync")
    gpu_url = _gpu_server_url(args)

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    files_to_check = [(args.pdf, "PDF")]
    if ref_audio:
        files_to_check.append((args.ref_audio, "Reference audio"))
    files_to_check.append((args.ref_video, "Reference video"))
    for path, label in files_to_check:
        if not os.path.isfile(path):
            print(f"Error: {label} not found: {path}", file=sys.stderr)
            return 1

    status_path = os.path.join(output_dir, args.status_file)
    if args.clean and os.path.exists(status_path):
        os.remove(status_path)

    tracker = ProcessingTracker(status_path)

    # -- extraction & chunking (page-aware for EPUB) --
    page_map = None
    if fmt == "epub":
        chunks, page_map = _extract_and_chunk_paged(
            args, tracker, max_chunk_bytes=backend.max_chunk_bytes,
        )
    else:
        chunks = _extract_and_chunk(args, tracker, max_chunk_bytes=backend.max_chunk_bytes)

    max_tts, sent_warn = _validation_limits(backend)
    chunks_to_process = _validate_and_collect(
        chunks, tracker, args.verbose,
        max_tts_bytes=max_tts, sentence_warn_bytes=sent_warn,
    )
    _synthesize_chunks(chunks_to_process, len(chunks), tracker, backend, output_dir, args.verbose)
    if _has_failed_chunks(tracker):
        print("Lipsync pipeline failed: one or more chunks did not complete.", file=sys.stderr)
        return 1

    # Align
    print("\n=== ALIGNMENT ===")
    aligned_chunks = _align_chunks(
        chunks, tracker, args,
        gpu_server_url=gpu_url,
        page_map=page_map,
    )

    if not aligned_chunks:
        print("No chunks to render.", file=sys.stderr)
        return 1

    # Lip-sync per chunk
    print("\n=== LIP-SYNC GENERATION ===")
    lipsync_clips = []
    lipsync_failed = False
    for ac in aligned_chunks:
        video_path = os.path.join(output_dir, VIDEO_CHUNK_FILE_PATTERN.format(num=ac.chunk_num))
        if tracker.is_video_rendered(ac.chunk_num):
            if args.verbose:
                print(f"  Chunk {ac.chunk_num}: lip-sync already rendered")
            lipsync_clips.append(video_path)
            continue

        print(f"  Generating lip-sync for chunk {ac.chunk_num}{'  (remote)' if gpu_url else ''}...")
        try:
            if gpu_url:
                from .remote_gpu import remote_generate_lipsync
                remote_generate_lipsync(
                    audio_path=ac.audio_path,
                    reference_video_path=args.ref_video,
                    output_path=video_path,
                    server_url=gpu_url,
                    provider=lipsync_provider,
                )
            else:
                from .lipsync import generate_lipsync_video
                generate_lipsync_video(
                    audio_path=ac.audio_path,
                    reference_video_path=args.ref_video,
                    output_path=video_path,
                    provider=lipsync_provider,
                    device=args.device,
                )
            tracker.mark_video_rendered(ac.chunk_num, video_path)
            lipsync_clips.append(video_path)
        except Exception as exc:
            print(f"  Lip-sync error for chunk {ac.chunk_num}: {exc}")
            lipsync_failed = True

    if lipsync_failed:
        print("Lipsync pipeline failed: one or more video chunks did not render.", file=sys.stderr)
        return 1

    if fmt == "epub":
        return _build_lipsync_epub(args, aligned_chunks, lipsync_clips, tracker, output_dir)
    else:
        return _build_lipsync_mp4(args, aligned_chunks, lipsync_clips, output_dir)


def _build_lipsync_epub(args, aligned_chunks, lipsync_clips, tracker, output_dir) -> int:
    """Assemble EPUB3 with Media Overlays + embedded lipsync videos."""
    from .epub_builder import EPUBBuilder

    output_file = args.output or (Path(args.pdf).stem + "_lipsync.epub")

    if tracker.is_epub_built() and not args.clean:
        dest = os.path.join(output_dir, output_file)
        print(f"\nEPUB already built: {dest}")
        return 0

    print("\n=== BUILDING EPUB ===")
    title = Path(args.pdf).stem.replace("_", " ").replace("-", " ").title()
    builder = EPUBBuilder(title=title, language=args.language)

    # Build a lookup from chunk_num to lipsync video path
    clip_map = {}
    for ac, clip in zip(aligned_chunks, lipsync_clips):
        clip_map[ac.chunk_num] = clip

    # Group chunks by their first page
    from collections import defaultdict
    page_chunks: dict = defaultdict(list)
    page_clips: dict = {}
    for ac in aligned_chunks:
        page = ac.pages[0] if ac.pages else 1
        page_chunks[page].append(ac)
        # Use the first available lipsync clip for each page
        if page not in page_clips and ac.chunk_num in clip_map:
            page_clips[page] = clip_map[ac.chunk_num]

    # For pages with multiple chunks, concatenate their lipsync videos
    for page_num in sorted(page_chunks):
        chunks_on_page = page_chunks[page_num]
        page_clip_paths = [clip_map[ac.chunk_num] for ac in chunks_on_page if ac.chunk_num in clip_map]

        video_path = None
        if len(page_clip_paths) == 1:
            video_path = page_clip_paths[0]
        elif len(page_clip_paths) > 1:
            # Concatenate per-chunk videos into one per-page video
            concat_path = os.path.join(output_dir, f"face_page_{page_num:03d}.mp4")
            try:
                concatenate(output_dir, concat_path, ext="mp4", files=page_clip_paths)
                video_path = concat_path
            except Exception as exc:
                print(f"  Warning: could not concat lipsync videos for page {page_num}: {exc}")
                video_path = page_clip_paths[0]

        builder.add_chapter(page_num, chunks_on_page, lipsync_video_path=video_path)

    dest = os.path.join(output_dir, output_file)
    builder.build(dest)
    tracker.mark_epub_built()
    print(f"\nDone: {dest}")
    return 0


def _build_lipsync_mp4(args, aligned_chunks, lipsync_clips, output_dir) -> int:
    """Compose MP4 video with face + highlighted text (legacy path)."""
    from .highlight_renderer import HighlightRenderer
    from .video_composer import compose_lipsync_video

    output_file = args.output or (Path(args.pdf).stem + "_lipsync.mp4")
    width, height = _parse_resolution(args.resolution)

    print("\n=== COMPOSING FINAL VIDEO ===")
    renderer = HighlightRenderer(
        width=width, height=height, font_size=args.font_size,
        highlight_color=DEFAULT_HIGHLIGHT_COLOR,
        text_color=DEFAULT_TEXT_COLOR,
        bg_color=DEFAULT_BG_COLOR,
    )

    dest = os.path.join(output_dir, output_file)
    compose_lipsync_video(
        aligned_chunks=aligned_chunks, lipsync_clips=lipsync_clips,
        renderer=renderer, output_path=dest,
        fps=args.fps, face_position=args.face_position,
    )
    print(f"\nDone: {dest}")
    return 0


def run_download_models(args) -> int:
    """Download ML model weights."""
    from .models import download_selected_models

    download_selected_models(args)
    return 0


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Backward compat: bare `screencastgen <file.pdf>` with no subcommand
    if args.command is None:
        compat_p = argparse.ArgumentParser(prog="screencastgen")
        _add_common_args(compat_p)
        _add_tts_backend_args(compat_p)
        compat_p.add_argument("-o", "--output", help="Output filename")
        compat_p.add_argument("--no-concat", action="store_true")
        compat_p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
        try:
            args = compat_p.parse_args(argv)
            args.command = "audio"
        except SystemExit:
            parser.print_help()
            return 1

    dispatch = {
        "audio": run_audio_pipeline,
        "highlight": run_highlight_pipeline,
        "lipsync": run_lipsync_pipeline,
        "download-models": run_download_models,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)
