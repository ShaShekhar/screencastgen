"""Command-line interface for screencastgen."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .constants import (
    DEFAULT_FONT_SIZE,
    DEFAULT_LANGUAGE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_STATUS_FILE,
    DEFAULT_VIDEO_FPS,
    DEFAULT_VIDEO_HEIGHT,
    DEFAULT_VIDEO_WIDTH,
    MAX_CHUNK_BYTES,
)
from .pipelines.audio import run_audio_pipeline as _run_audio_pipeline_impl
from .pipelines.common import (
    align_chunks as _align_chunks_impl,
    create_tts_backend as _create_tts_backend_impl,
    extract_and_chunk as _extract_and_chunk_impl,
    extract_and_chunk_paged as _extract_and_chunk_paged_impl,
    gpu_server_url as _gpu_server_url_impl,
    synthesize_chunks as _synthesize_chunks_impl,
    validation_limits as _validation_limits_impl,
    validate_and_collect as _validate_and_collect_impl,
)
from .pipelines.highlight import parse_resolution as _parse_resolution_impl
from .pipelines.highlight import run_highlight_pipeline as _run_highlight_pipeline_impl
from .pipelines.lipsync import run_lipsync_pipeline as _run_lipsync_pipeline_impl
from .pipelines.visualization import run_visualization_pipeline as _run_visualization_pipeline_impl


def _add_common_args(p: argparse.ArgumentParser) -> None:
    """Add arguments shared by all subcommands."""
    p.add_argument("pdf", help="Path to the input document file (PDF, TXT, Markdown, or EPUB)")
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
    from .providers.tts import get_backend_names, get_default_backend_name, register_backend_args

    p.add_argument(
        "--backend",
        default=get_default_backend_name(context="cli"),
        choices=get_backend_names(context="cli"),
        help="TTS backend",
    )
    p.add_argument("--device", default="auto", help="Device for local models: auto, cpu, or cuda (default: auto)")
    p.add_argument("--voice", default=None, help="Voice name (backend-specific)")
    p.add_argument("--ref-audio", default=None, help="Reference audio for voice cloning backends")
    p.add_argument("--ref-text", default=None, help="Transcript of reference audio")
    p.add_argument(
        "--tts-concurrency",
        type=int,
        default=1,
        help="Number of chunks to synthesize in parallel (default: 1). "
        "Raise this with --backend remote when the server has a pool of workers.",
    )
    p.add_argument(
        "--tts-timeout",
        type=int,
        default=300,
        help="Socket timeout in seconds for remote TTS synthesis requests (default: 300).",
    )
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


def _add_visualization_args(p: argparse.ArgumentParser) -> None:
    """Add arguments for generated math visualization rendering."""
    from .providers.visualization import get_default_renderer_name, get_renderer_names

    p.add_argument("--prompt", required=True, help="Concept prompt to visualize")
    p.add_argument(
        "-o",
        "--output",
        help="Output MP4 filename inside --output-dir (default: visualization.mp4)",
    )
    p.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for generated source and render output (default: {DEFAULT_OUTPUT_DIR})",
    )
    p.add_argument(
        "--renderer",
        "--provider",
        dest="provider",
        default=get_default_renderer_name(),
        choices=get_renderer_names(),
        help="Visualization renderer provider",
    )
    p.add_argument(
        "--duration",
        "--duration-seconds",
        dest="duration_seconds",
        type=int,
        default=30,
        help="Target animation duration in seconds (default: 30)",
    )
    p.add_argument(
        "--resolution",
        default=f"{DEFAULT_VIDEO_WIDTH}x{DEFAULT_VIDEO_HEIGHT}",
        help=f"Video resolution WxH (default: {DEFAULT_VIDEO_WIDTH}x{DEFAULT_VIDEO_HEIGHT})",
    )
    p.add_argument("--fps", type=int, default=DEFAULT_VIDEO_FPS, help=f"Frame rate (default: {DEFAULT_VIDEO_FPS})")
    p.add_argument(
        "--style",
        default="clean",
        choices=["clean", "chalkboard", "blueprint", "minimal"],
        help="Visual style preset (default: clean)",
    )
    p.add_argument(
        "--audience-level",
        default="general",
        help="Audience level used in generated scene labels (default: general)",
    )
    p.add_argument("--timeout", dest="timeout_seconds", type=int, default=300, help="Render timeout in seconds")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose output")


def _add_provider_args(p: argparse.ArgumentParser, *, include_lipsync: bool = False) -> None:
    """Add alignment and lip-sync provider selection args."""
    from .aligner import get_alignment_provider_names, get_default_alignment_provider

    p.add_argument(
        "--aligner",
        default=get_default_alignment_provider(),
        choices=get_alignment_provider_names(),
        help="Alignment provider",
    )

    if include_lipsync:
        from .lipsync import get_default_lipsync_provider, get_lipsync_provider_names

        p.add_argument(
            "--lipsync-provider",
            default=get_default_lipsync_provider(),
            choices=get_lipsync_provider_names(),
            help="Lip-sync provider",
        )


def _parse_resolution(res_str: str) -> tuple:
    return _parse_resolution_impl(res_str)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="screencastgen",
        description="Convert PDF documents to audio and video.",
    )
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")

    sub = p.add_subparsers(dest="command")

    audio_p = sub.add_parser("audio", help="Convert PDF to audio (default)")
    _add_common_args(audio_p)
    _add_tts_backend_args(audio_p)
    audio_p.add_argument("-o", "--output", help="Output audio filename (default: <pdf-stem>.<ext>)")
    audio_p.add_argument("--no-concat", action="store_true", help="Skip final concatenation step")

    hl_p = sub.add_parser("highlight", help="Create highlighted-text video from PDF")
    _add_common_args(hl_p)
    _add_tts_backend_args(hl_p)
    _add_provider_args(hl_p)
    _add_video_args(hl_p)
    hl_p.add_argument("-o", "--output", help="Output filename (default: <pdf-stem>_highlight.epub)")
    hl_p.add_argument("--format", default="epub", choices=["epub", "mp4"], help="Output format (default: epub)")

    ls_p = sub.add_parser("lipsync", help="Create lip-synced video with voice cloning")
    _add_common_args(ls_p)
    _add_tts_backend_args(ls_p)
    _add_provider_args(ls_p, include_lipsync=True)
    _add_video_args(ls_p)
    ls_p.add_argument("-o", "--output", help="Output filename (default: <document-stem>_reader.zip)")
    ls_p.add_argument("--ref-video", required=True, help="Reference face video clip (~10s)")
    ls_p.add_argument(
        "--format",
        default="reader",
        choices=["epub", "mp4", "reader"],
        help="Output format: reader (standalone offline ZIP), mp4 (baked composite), "
        "or epub (text + narration accessibility export) (default: reader)",
    )
    ls_p.add_argument(
        "--face-position",
        default="bottom-right",
        choices=[
            "left",
            "right",
            "center",
            "top-left",
            "top-right",
            "bottom-left",
            "bottom-right",
        ],
        help="Position of the face in the video (default: bottom-right)",
    )
    ls_p.add_argument(
        "--face-scale",
        type=float,
        default=0.22,
        help="Relative face width for docked corner layouts (default: 0.22)",
    )
    ls_p.add_argument(
        "--latentsync-preset",
        default="quality",
        choices=["small", "quality"],
        help="LatentSync preset: small (256) or quality (512) (default: quality)",
    )

    viz_p = sub.add_parser("visualize", help="Create a generated educational math animation")
    _add_visualization_args(viz_p)

    from .models import register_model_download_args

    dm_p = sub.add_parser("download-models", help="Pre-download ML model weights")
    register_model_download_args(dm_p)

    doctor_p = sub.add_parser("doctor", help="Check installation and runtime prerequisites")
    doctor_p.add_argument(
        "--profile",
        choices=("auto", "local-gpu", "remote-client", "dev"),
        default="auto",
        help="Capability profile to check (default: auto)",
    )
    doctor_p.add_argument("--model", choices=("0.6B", "1.7B"), default="0.6B")
    doctor_p.add_argument("--server-url", help="Remote GPU server URL to verify")

    return p


def _create_tts_backend(args, invocation: str):
    """Compatibility wrapper for tests and CLI patching."""
    try:
        return _create_tts_backend_impl(args, invocation)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


def _extract_and_chunk(args, tracker, max_chunk_bytes=MAX_CHUNK_BYTES):
    return _extract_and_chunk_impl(args, tracker, max_chunk_bytes=max_chunk_bytes)


def _extract_and_chunk_paged(args, tracker, max_chunk_bytes=MAX_CHUNK_BYTES):
    return _extract_and_chunk_paged_impl(args, tracker, max_chunk_bytes=max_chunk_bytes)


def _validate_and_collect(chunks, tracker, verbose=False, max_tts_bytes=None, sentence_warn_bytes=None):
    return _validate_and_collect_impl(
        chunks,
        tracker,
        verbose=verbose,
        max_tts_bytes=max_tts_bytes,
        sentence_warn_bytes=sentence_warn_bytes,
    )


def _synthesize_chunks(chunks_to_process, total_chunks, tracker, backend, output_dir, verbose=False):
    return _synthesize_chunks_impl(
        chunks_to_process,
        total_chunks,
        tracker,
        backend,
        output_dir,
        verbose=verbose,
    )


def _align_chunks(chunks, tracker, args, gpu_server_url=None, page_map=None):
    return _align_chunks_impl(chunks, tracker, args, gpu_server_url=gpu_server_url, page_map=page_map)


def _gpu_server_url(args):
    return _gpu_server_url_impl(args)


def _validation_limits(backend):
    return _validation_limits_impl(backend)


def run_audio_pipeline(args) -> int:
    return _run_audio_pipeline_impl(args, backend_factory=_create_tts_backend).exit_code


def run_highlight_pipeline(args) -> int:
    return _run_highlight_pipeline_impl(args, backend_factory=_create_tts_backend).exit_code


def run_lipsync_pipeline(args) -> int:
    return _run_lipsync_pipeline_impl(args, backend_factory=_create_tts_backend).exit_code


def run_visualization_pipeline(args) -> int:
    return _run_visualization_pipeline_impl(args).exit_code


def run_download_models(args) -> int:
    """Download ML model weights."""
    from .models import download_selected_models

    try:
        download_selected_models(args)
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def run_doctor(args) -> int:
    """Check the active installation without changing it."""
    from .doctor import run_doctor as _run_doctor

    return _run_doctor(args.profile, args.model, args.server_url)


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

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
        "visualize": run_visualization_pipeline,
        "download-models": run_download_models,
        "doctor": run_doctor,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)
