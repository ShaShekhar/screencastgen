"""GPU inference server — serves TTS, alignment, and lip-sync.

Run on the GPU VM::

    pip install -e ".[server]"
    screencastgen-server --backend qwen --device cuda

The CPU VM connects via SSH tunnel::

    ssh -L 8100:localhost:8100 gpu-vm

Then uses ``--backend remote`` in the CLI or web app.

Endpoints
---------
POST /synthesize   — Text → audio (WAV/MP3)
POST /align        — Audio + text → word-level timestamps (JSON)
POST /lipsync      — Audio + reference video → lip-synced video
GET  /health       — Readiness and backend info
"""

import argparse
import io
import json
import os
import sys
import tempfile
from typing import Optional

# ---------------------------------------------------------------------------
# Server state — populated by startup
# ---------------------------------------------------------------------------
_backend = None
_backend_name: str = ""
_device: str = "auto"
_aligner_name: str = "whisperx"
_lipsync_provider_name: str = "auto"


def _create_app():
    """Build the FastAPI application (deferred so imports are optional)."""
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.responses import Response

    from pydantic import BaseModel

    app = FastAPI(title="screencastgen GPU inference server")

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.get("/health")
    def health():
        return {
            "status": "ok" if _backend is not None else "not_ready",
            "backend": _backend_name,
            "output_format": _backend.output_format if _backend else None,
            "max_chunk_bytes": _backend.max_chunk_bytes if _backend else None,
            "device": _device,
            "aligner": _aligner_name,
            "lipsync_provider": _lipsync_provider_name,
            "capabilities": ["synthesize", "align", "lipsync"],
        }

    # ------------------------------------------------------------------
    # TTS synthesis
    # ------------------------------------------------------------------

    class SynthesizeRequest(BaseModel):
        text: str
        language: str = "en-US"

    @app.post("/synthesize")
    def synthesize(req: SynthesizeRequest):
        if _backend is None:
            raise HTTPException(503, "Backend not initialized")

        ext = _backend.output_format
        fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}")
        os.close(fd)

        try:
            _backend.synthesize(req.text, tmp_path)
            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        media_type = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
        }.get(ext, "application/octet-stream")

        return Response(content=audio_bytes, media_type=media_type)

    # ------------------------------------------------------------------
    # Alignment
    # ------------------------------------------------------------------

    @app.post("/align")
    async def align(
        audio: UploadFile = File(...),
        text: str = Form(...),
        language: str = Form("en-US"),
        provider: Optional[str] = Form(None),
    ):
        """Align text to audio and return word-level timestamps."""
        from .aligner import align_chunk

        # Save uploaded audio to a temp file
        suffix = os.path.splitext(audio.filename or "audio.wav")[1] or ".wav"
        fd, tmp_audio = tempfile.mkstemp(suffix=suffix)
        os.close(fd)

        try:
            content = await audio.read()
            with open(tmp_audio, "wb") as f:
                f.write(content)

            words = align_chunk(
                tmp_audio,
                text,
                provider=provider or _aligner_name,
                language=language,
                device=_device,
            )

            return {
                "words": [
                    {"word": w.word, "start": w.start, "end": w.end}
                    for w in words
                ]
            }
        finally:
            if os.path.exists(tmp_audio):
                os.unlink(tmp_audio)

    # ------------------------------------------------------------------
    # Lip-sync video generation
    # ------------------------------------------------------------------

    @app.post("/lipsync")
    async def lipsync(
        audio: UploadFile = File(...),
        reference_video: UploadFile = File(...),
        provider: Optional[str] = Form(None),
    ):
        """Generate lip-synced video from audio and reference face video."""
        from .lipsync import generate_lipsync_video

        # Save uploaded files to temp paths
        audio_suffix = os.path.splitext(audio.filename or "audio.wav")[1] or ".wav"
        video_suffix = os.path.splitext(reference_video.filename or "ref.mp4")[1] or ".mp4"

        fd_a, tmp_audio = tempfile.mkstemp(suffix=audio_suffix)
        os.close(fd_a)
        fd_v, tmp_video = tempfile.mkstemp(suffix=video_suffix)
        os.close(fd_v)
        fd_o, tmp_output = tempfile.mkstemp(suffix=".mp4")
        os.close(fd_o)

        try:
            audio_content = await audio.read()
            with open(tmp_audio, "wb") as f:
                f.write(audio_content)

            video_content = await reference_video.read()
            with open(tmp_video, "wb") as f:
                f.write(video_content)

            generate_lipsync_video(
                audio_path=tmp_audio,
                reference_video_path=tmp_video,
                output_path=tmp_output,
                provider=provider or _lipsync_provider_name,
                device=_device,
            )

            with open(tmp_output, "rb") as f:
                result_bytes = f.read()

            return Response(content=result_bytes, media_type="video/mp4")
        finally:
            for p in (tmp_audio, tmp_video, tmp_output):
                if os.path.exists(p):
                    os.unlink(p)

    return app


app = _create_app()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_server_parser() -> argparse.ArgumentParser:
    from .backends import (
        get_backend_names,
        get_default_backend_name,
        register_backend_args,
    )
    from .aligner import (
        get_alignment_provider_names,
        get_default_alignment_provider,
    )
    from .lipsync import (
        get_lipsync_provider_names,
        get_default_lipsync_provider,
    )

    p = argparse.ArgumentParser(
        prog="screencastgen-server",
        description="GPU inference server — TTS, alignment, and lip-sync.",
    )
    p.add_argument(
        "--backend",
        default=get_default_backend_name(context="server"),
        choices=get_backend_names(context="server"),
        help="TTS backend to load",
    )
    p.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    p.add_argument("--port", type=int, default=8100, help="Port (default: 8100)")
    p.add_argument("--device", default="auto", help="Device: auto, cpu, cuda (default: auto)")
    p.add_argument("--language", default="en-US", help="Default language code (default: en-US)")
    # Voice cloning reference (stays loaded for all requests)
    p.add_argument("--ref-audio", default=None, help="Reference audio for voice cloning")
    p.add_argument("--ref-text", default=None, help="Transcript of reference audio")
    p.add_argument(
        "--aligner",
        default=get_default_alignment_provider(),
        choices=get_alignment_provider_names(),
        help="Alignment provider to use for /align requests",
    )
    p.add_argument(
        "--lipsync-provider",
        default=get_default_lipsync_provider(),
        choices=get_lipsync_provider_names(),
        help="Lip-sync provider to use for /lipsync requests",
    )
    register_backend_args(p, context="server")
    return p


def main(argv=None):
    global _backend, _backend_name, _device, _aligner_name, _lipsync_provider_name

    parser = _build_server_parser()
    args = parser.parse_args(argv)

    # Resolve device
    from .backends.base import resolve_device
    _device = resolve_device(args.device)

    # Build the TTS backend eagerly so the model is loaded before serving
    from .backends import create_backend_from_args

    _backend_name = args.backend
    _aligner_name = args.aligner
    _lipsync_provider_name = args.lipsync_provider

    print(f"Loading {args.backend} TTS backend on {_device}...")
    try:
        _backend = create_backend_from_args(args, invocation="server")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    # Force model load now (not on first request)
    if hasattr(_backend, "_ensure_model"):
        _backend._ensure_model()

    print(f"Backend ready. Serving on {args.host}:{args.port}")
    print(f"Capabilities: TTS synthesis, alignment, lip-sync generation")

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
