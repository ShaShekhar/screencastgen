"""Shared helpers for pipeline runners."""

from __future__ import annotations

import os
import re
from typing import Any, Optional

from ..constants import CHUNK_FILE_PATTERN, MAX_CHUNK_BYTES
from ..extractor import extract_text, extract_text_by_page
from ..text_processing import (
    create_chunks,
    create_chunks_with_pages,
    preprocess_text,
    split_into_sentences,
    split_into_sentences_by_page,
    validate_chunk,
)
from ..tracker import ProcessingTracker, compute_chunk_hash
from .events import PipelineReporter


def get_reporter(reporter: Optional[PipelineReporter]) -> PipelineReporter:
    """Return *reporter* or a default console reporter."""
    return reporter if reporter is not None else PipelineReporter()


def create_tts_backend(args: Any, invocation: str):
    """Build the appropriate TTSBackend from parsed args."""
    from ..providers.tts import create_backend_from_args

    return create_backend_from_args(args, invocation=invocation)


def extract_and_chunk(args, tracker, max_chunk_bytes=MAX_CHUNK_BYTES, reporter: Optional[PipelineReporter] = None):
    """Steps 1-4: extract, preprocess, split, and chunk."""
    reporter = get_reporter(reporter)
    pdf_path = args.pdf
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"{pdf_path} not found")

    if tracker.status["total_chunks"] > 0 and not args.clean:
        summary = tracker.get_summary()
        reporter.line("=== RESUMING PREVIOUS SESSION ===")
        reporter.line(f"Total chunks: {summary['total']}")
        reporter.line(f"Already processed: {summary['processed']}")
        reporter.line(f"Failed: {summary['failed']}")
        reporter.line(f"Remaining: {summary['remaining']}")

    reporter.phase_start("extracting", "\nStep 1: Extracting text from PDF...")
    raw_text = extract_text(pdf_path)

    reporter.phase_start("preprocessing", "Step 2: Preprocessing text...")
    processed = preprocess_text(raw_text)

    reporter.phase_start("splitting", "Step 3: Splitting into sentences...")
    sentences = split_into_sentences(processed)

    reporter.phase_start("chunking", "Step 4: Creating chunks...")
    chunks = create_chunks(sentences, max_bytes=max_chunk_bytes)
    reporter.line(f"Created {len(chunks)} chunks")
    reporter.emit(total=len(chunks))

    tracker.status["total_chunks"] = len(chunks)
    tracker.save()

    return chunks


def extract_and_chunk_paged(
    args,
    tracker,
    max_chunk_bytes=MAX_CHUNK_BYTES,
    reporter: Optional[PipelineReporter] = None,
):
    """Page-aware extraction and chunking for EPUB output."""
    reporter = get_reporter(reporter)
    pdf_path = args.pdf
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"{pdf_path} not found")

    if tracker.status["total_chunks"] > 0 and not args.clean:
        summary = tracker.get_summary()
        reporter.line("=== RESUMING PREVIOUS SESSION ===")
        reporter.line(f"Total chunks: {summary['total']}")
        reporter.line(f"Already processed: {summary['processed']}")
        reporter.line(f"Failed: {summary['failed']}")
        reporter.line(f"Remaining: {summary['remaining']}")

    reporter.phase_start("extracting", "\nStep 1: Extracting text from PDF (page-aware)...")
    pages = extract_text_by_page(pdf_path)

    reporter.phase_start("splitting", "Step 2-3: Preprocessing and splitting per page...")
    page_sentences = split_into_sentences_by_page(pages)

    reporter.phase_start("chunking", "Step 4: Creating chunks (preserving page info)...")
    chunks_with_pages = create_chunks_with_pages(page_sentences, max_bytes=max_chunk_bytes)

    chunks = [text for text, _pages in chunks_with_pages]
    page_map = {i + 1: pg for i, (_, pg) in enumerate(chunks_with_pages)}

    reporter.line(f"Created {len(chunks)} chunks across {len(pages)} pages")
    reporter.emit(total=len(chunks))

    tracker.status["total_chunks"] = len(chunks)
    tracker.save()

    return chunks, page_map


def validate_and_collect(
    chunks,
    tracker,
    verbose=False,
    max_tts_bytes=None,
    sentence_warn_bytes=None,
    reporter: Optional[PipelineReporter] = None,
):
    """Step 5: validate chunks and collect the ones that should run."""
    reporter = get_reporter(reporter)
    reporter.phase_start("validating", "\nStep 5: Validating chunks...")

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
                reporter.line(f"  Chunk {chunk_num}: already processed")
            continue

        is_valid, issues = validate_chunk(chunk, chunk_num, **validate_kwargs)
        if is_valid:
            chunks_to_process.append((chunk_num, chunk, chunk_hash))
        else:
            reporter.line(f"\n  Chunk {chunk_num} FAILED validation:")
            for issue in issues:
                reporter.line(f"    - {issue}")
            tracker.mark_failed(chunk_num, chunk_hash, "; ".join(issues))

    reporter.line(f"\nChunks to process: {len(chunks_to_process)}")
    return chunks_to_process


def synthesize_chunks(
    chunks_to_process,
    total_chunks,
    tracker,
    backend,
    output_dir,
    verbose=False,
    reporter: Optional[PipelineReporter] = None,
):
    """Synthesize audio chunks using the provided backend."""
    reporter = get_reporter(reporter)
    if not chunks_to_process:
        summary = tracker.get_summary()
        reporter.line("\nAll chunks already processed or failed validation.")
        reporter.line(
            f"  Total: {summary['total']}  Processed: {summary['processed']}  Failed: {summary['failed']}"
        )
        return 0

    ext = backend.output_format
    processed_count = 0
    for chunk_num, chunk, chunk_hash in chunks_to_process:
        chunk_file = os.path.join(output_dir, CHUNK_FILE_PATTERN.format(num=chunk_num, ext=ext))
        reporter.line(f"\nProcessing chunk {chunk_num}/{total_chunks}...")
        reporter.emit(phase="synthesizing", current=chunk_num, total=total_chunks)
        if verbose:
            reporter.line(f"  Size: {len(chunk.encode('utf-8'))} bytes")
            reporter.line(f"  Preview: {chunk[:80]}...")

        try:
            backend.synthesize(chunk, chunk_file)
            tracker.mark_processed(chunk_num, chunk_hash, chunk_file)
            processed_count += 1
            reporter.line(f"  Created {chunk_file}")
        except Exception as exc:
            error_msg = str(exc)
            reporter.line(f"  Error: {error_msg}")
            tracker.mark_failed(chunk_num, chunk_hash, error_msg)

            if "sentence" in error_msg.lower() and "too long" in error_msg.lower():
                for j, sent in enumerate(re.split(r"(?<=[.!?])\s*", chunk)):
                    if sent.strip() and len(sent.encode("utf-8")) > 850:
                        reporter.line(f"    Sentence {j + 1}: {len(sent.encode('utf-8'))} bytes")

    summary = tracker.get_summary()
    reporter.line("\n=== SYNTHESIS COMPLETE ===")
    reporter.line(f"Processed this session: {processed_count}")
    reporter.line(f"Total processed: {summary['processed']}/{summary['total']}")
    reporter.line(f"Failed: {summary['failed']}")

    if summary["failed"] > 0:
        reporter.line("\nFailed chunks:")
        for cnum, details in tracker.status["failed_chunks"].items():
            reporter.line(f"  Chunk {cnum}: {details['error']}")
        reporter.line("Re-run the command to retry failed chunks.")

    return processed_count


def has_failed_chunks(tracker) -> bool:
    """Return True when any chunk failed validation or synthesis."""
    return tracker.get_summary()["failed"] > 0


def align_chunks(
    chunks,
    tracker,
    args,
    gpu_server_url=None,
    page_map=None,
    reporter: Optional[PipelineReporter] = None,
):
    """Run alignment on all processed chunks."""
    from ..aligner import get_default_alignment_provider
    from ..types import AlignedChunk, WordTiming

    reporter = get_reporter(reporter)
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
                reporter.line(f"  Chunk {chunk_num}: already aligned")
            words_data = tracker.get_alignment(chunk_num)
            words = [WordTiming(w["word"], w["start"], w["end"]) for w in words_data]
        else:
            reporter.line(f"  Aligning chunk {chunk_num}{'  (remote)' if use_remote else ''}...")
            reporter.emit(phase="aligning", current=chunk_num, total=len(chunks))
            try:
                if use_remote:
                    from ..remote_gpu import remote_align_chunk

                    words = remote_align_chunk(
                        audio_path,
                        chunk,
                        server_url=gpu_server_url,
                        language=args.language,
                        provider=aligner_name,
                    )
                else:
                    from ..aligner import align_chunk

                    words = align_chunk(
                        audio_path,
                        chunk,
                        provider=aligner_name,
                        language=args.language,
                        device=getattr(args, "device", "auto"),
                    )
                tracker.mark_aligned(chunk_num, words)
            except Exception as exc:
                reporter.line(f"  Alignment error for chunk {chunk_num}: {exc}")
                words = []

        pages = page_map.get(chunk_num, []) if page_map else []
        aligned_chunks.append(
            AlignedChunk(
                chunk_num=chunk_num,
                text=chunk,
                audio_path=audio_path,
                words=words,
                pages=pages,
            )
        )

    return aligned_chunks


def gpu_server_url(args):
    """Return the GPU server URL if the backend is remote, else None."""
    if getattr(args, "backend", None) == "remote":
        return getattr(args, "tts_server_url", "http://localhost:8100")
    return None


def validation_limits(backend):
    """Return (max_tts_bytes, sentence_warn_bytes) for *backend*."""
    from ..constants import MAX_TTS_BYTES, SENTENCE_WARN_BYTES

    max_tts = backend.max_chunk_bytes
    if max_tts > MAX_TTS_BYTES:
        return max_tts, max_tts
    return MAX_TTS_BYTES, SENTENCE_WARN_BYTES


def status_path(output_dir: str, status_file: str) -> str:
    """Return the resume-state path inside *output_dir*."""
    return os.path.join(output_dir, status_file)


def prepare_tracker(args) -> ProcessingTracker:
    """Create a tracker and apply the --clean option."""
    os.makedirs(args.output_dir, exist_ok=True)
    tracker_path = status_path(args.output_dir, args.status_file)
    if args.clean and os.path.exists(tracker_path):
        os.remove(tracker_path)
    return ProcessingTracker(tracker_path)


def build_title(pdf_path: str) -> str:
    """Convert a PDF filename into a human-readable title."""
    from pathlib import Path

    return Path(pdf_path).stem.replace("_", " ").replace("-", " ").title()
