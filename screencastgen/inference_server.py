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
import threading
from typing import Optional

# ---------------------------------------------------------------------------
# Server state — populated by startup
# ---------------------------------------------------------------------------
_backend = None
_backend_name: str = ""
_device: str = "auto"
_aligner_name: str = "whisperx"
_lipsync_provider_name: str = "auto"

# Serializes per-request voice overrides on the shared backend instance.
_synthesize_lock = threading.Lock()


def _create_app():
    """Build the FastAPI application (deferred so imports are optional)."""
    from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
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

    def _media_type_for(ext: str) -> str:
        return {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
        }.get(ext, "application/octet-stream")

    def _run_synthesis(
        text: str,
        language: str,
        ref_audio_bytes: Optional[bytes],
        ref_audio_filename: Optional[str],
        ref_text: Optional[str],
    ) -> bytes:
        """Invoke the backend, optionally overriding the reference voice.

        Per-request reference overrides mutate the backend instance under
        ``_synthesize_lock`` and are reverted in a finally block so concurrent
        requests don't see each other's voices.
        """
        if _backend is None:
            raise HTTPException(503, "Backend not initialized")

        ext = _backend.output_format
        fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}")
        os.close(fd)

        ref_tmp_path: Optional[str] = None
        try:
            if ref_audio_bytes:
                suffix = (
                    os.path.splitext(ref_audio_filename or "ref.wav")[1] or ".wav"
                )
                fd_ref, ref_tmp_path = tempfile.mkstemp(suffix=suffix)
                os.close(fd_ref)
                with open(ref_tmp_path, "wb") as f:
                    f.write(ref_audio_bytes)

            with _synthesize_lock:
                # Update language if the backend exposes it.
                prev_language = getattr(_backend, "_language", None)
                if hasattr(_backend, "_language"):
                    # Qwen backend stores a normalized label keyed by code.
                    from .providers.tts.qwen_backend import _LANG_MAP

                    _backend._language = _LANG_MAP.get(language.lower(), prev_language)

                # Override reference voice for this request only.
                prev_ref_audio = getattr(_backend, "ref_audio_path", None)
                prev_ref_text = getattr(_backend, "ref_text", None)
                if ref_tmp_path is not None and hasattr(_backend, "ref_audio_path"):
                    _backend.ref_audio_path = ref_tmp_path
                    if hasattr(_backend, "ref_text"):
                        _backend.ref_text = ref_text

                try:
                    _backend.synthesize(text, tmp_path)
                finally:
                    if hasattr(_backend, "_language"):
                        _backend._language = prev_language
                    if ref_tmp_path is not None and hasattr(_backend, "ref_audio_path"):
                        _backend.ref_audio_path = prev_ref_audio
                        if hasattr(_backend, "ref_text"):
                            _backend.ref_text = prev_ref_text

            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            if ref_tmp_path and os.path.exists(ref_tmp_path):
                os.unlink(ref_tmp_path)

    @app.post("/synthesize")
    async def synthesize(request: Request):
        """Synthesize text to audio.

        Accepts either application/json (``{text, language}``) or
        multipart/form-data with optional ``ref_audio`` (file) and
        ``ref_text`` (string) fields for per-request voice cloning.
        """
        if _backend is None:
            raise HTTPException(503, "Backend not initialized")

        content_type = (request.headers.get("content-type") or "").lower()

        if content_type.startswith("multipart/"):
            form = await request.form()
            text = str(form.get("text") or "").strip()
            if not text:
                raise HTTPException(400, "Missing 'text' field")
            language = str(form.get("language") or "en-US")
            ref_text_value = form.get("ref_text")
            ref_text = str(ref_text_value) if ref_text_value is not None else None
            ref_audio_field = form.get("ref_audio")
            ref_audio_bytes: Optional[bytes] = None
            ref_audio_filename: Optional[str] = None
            if ref_audio_field is not None and hasattr(ref_audio_field, "read"):
                ref_audio_bytes = await ref_audio_field.read()
                ref_audio_filename = getattr(ref_audio_field, "filename", None)
        else:
            payload = await request.json()
            try:
                req = SynthesizeRequest(**payload)
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(400, f"Invalid JSON body: {exc}") from exc
            text = req.text
            language = req.language
            ref_text = None
            ref_audio_bytes = None
            ref_audio_filename = None

        audio_bytes = _run_synthesis(
            text=text,
            language=language,
            ref_audio_bytes=ref_audio_bytes,
            ref_audio_filename=ref_audio_filename,
            ref_text=ref_text,
        )
        return Response(content=audio_bytes, media_type=_media_type_for(_backend.output_format))

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
        latentsync_preset: str = Form("quality"),
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
                latentsync_preset=latentsync_preset,
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
    from .providers.tts import (
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
    from .providers.tts.base import resolve_device
    _device = resolve_device(args.device)

    # Build the TTS backend eagerly so the model is loaded before serving
    from .providers.tts import create_backend_from_args

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
