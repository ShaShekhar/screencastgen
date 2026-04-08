"""Audio pipeline runner."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Optional

from ..concatenator import concatenate
from .common import (
    create_tts_backend,
    extract_and_chunk,
    get_reporter,
    has_failed_chunks,
    prepare_tracker,
    synthesize_chunks,
    validation_limits,
    validate_and_collect,
)
from .events import PipelineReporter
from .types import AudioPipelineRequest, PipelineRunResult, coerce_request


BackendFactory = Callable[[object, str], object]


def run_audio_pipeline(
    request,
    *,
    reporter: Optional[PipelineReporter] = None,
    backend_factory: Optional[BackendFactory] = None,
) -> PipelineRunResult:
    """Run the audio-only pipeline."""
    reporter = get_reporter(reporter)
    request = coerce_request(AudioPipelineRequest, request)
    factory = backend_factory or create_tts_backend

    try:
        backend = factory(request, "audio")
    except SystemExit as exc:
        return PipelineRunResult(exit_code=int(exc.code or 1))
    except Exception as exc:
        reporter.line(str(exc))
        return PipelineRunResult(exit_code=1, error_message=str(exc))

    ext = backend.output_format
    output_name = request.output or (Path(request.pdf).stem + f".{ext}")
    request.output = output_name

    try:
        tracker = prepare_tracker(request)
        chunks = extract_and_chunk(request, tracker, max_chunk_bytes=backend.max_chunk_bytes, reporter=reporter)
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
            msg = "Audio pipeline failed: one or more chunks did not complete."
            reporter.line(msg)
            return PipelineRunResult(exit_code=1, output_name=output_name, error_message=msg)

        dest = os.path.join(request.output_dir, output_name)
        if not request.no_concat:
            summary = tracker.get_summary()
            if summary["processed"] > 0:
                reporter.phase_start("concatenating", f"\nConcatenating into {dest}...")
                try:
                    concatenate(request.output_dir, dest, ext=ext)
                    reporter.line(f"Done: {dest}")
                except FileNotFoundError as exc:
                    reporter.line(f"Skipping concatenation: {exc}")
                    return PipelineRunResult(exit_code=1, output_name=output_name, error_message=str(exc))
                except Exception as exc:
                    reporter.line(f"Concatenation failed: {exc}")
                    return PipelineRunResult(exit_code=1, output_name=output_name, error_message=str(exc))
                if not os.path.isfile(dest):
                    msg = f"Concatenation failed: output file missing at {dest}"
                    print(msg, file=sys.stderr)
                    return PipelineRunResult(exit_code=1, output_name=output_name, error_message=msg)
            else:
                msg = "Audio pipeline failed: no synthesized chunks were produced."
                print(msg, file=sys.stderr)
                return PipelineRunResult(exit_code=1, output_name=output_name, error_message=msg)

        return PipelineRunResult(exit_code=0, output_name=output_name, output_path=dest if not request.no_concat else None)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return PipelineRunResult(exit_code=1, output_name=output_name, error_message=str(exc))
