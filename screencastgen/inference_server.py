"""GPU inference server — serves TTS, alignment, and lip-sync.

Run on the GPU VM::

    pip install -e ".[server]"
    screencastgen-server --backend qwen --device cuda

The CPU VM connects via SSH tunnel::

    ssh -L 8100:localhost:8100 gpu-vm

Then uses ``--backend remote`` in the CLI or web app.

Endpoints
---------
POST   /synthesize          — Text → audio (WAV/MP3)
POST   /transcribe          — Audio → plain text (WhisperX)
POST   /align               — Audio + text → word-level timestamps (JSON)
POST   /lipsync             — Queue a lip-sync job → JSON job handle
GET    /lipsync/{id}        — Lip-sync job status + elapsed seconds
GET    /lipsync/{id}/result — Download the finished lip-synced video
POST   /lipsync/{id}/cancel — Request cancellation of a lip-sync job
DELETE /lipsync/{id}        — Discard a lip-sync job and its output
GET    /health              — Readiness and backend info
"""

import argparse
import asyncio
import os
import sys
import tempfile
import threading
import time
import uuid
from typing import Optional

# ---------------------------------------------------------------------------
# Server state — populated by startup
# ---------------------------------------------------------------------------
_backend = None
_batcher = None                         # BatchingSynthesizer; set in main()
_backend_name: str = ""
_device: str = "auto"
_aligner_name: str = "whisperx"
_lipsync_provider_name: str = "auto"

# Async lip-sync jobs: clients submit work, then poll. Generation runs in a
# background thread so a slow GPU never holds an HTTP connection open (which
# would otherwise trip the client's socket timeout). The GPU lock serialises
# TTS, transcription, alignment, and lip-sync so model handoffs can release VRAM
# before the next GPU-heavy phase starts.
_lipsync_jobs: dict = {}
_lipsync_jobs_lock = threading.Lock()
_lipsync_gpu_lock = threading.Lock()


def _safe_unlink(path: Optional[str]) -> None:
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def _release_tts_backend_for_gpu_phase(phase: str) -> None:
    """Unload the TTS model so another GPU-heavy phase can use VRAM."""
    backend = _backend
    close = getattr(backend, "close", None)
    if close is None:
        return

    try:
        close()
        print(f"Released TTS backend GPU memory before {phase}.")
    except Exception as exc:  # noqa: BLE001 - lip-sync can still attempt to run
        print(f"WARNING: could not release TTS backend GPU memory: {exc}", file=sys.stderr)


def _run_lipsync_job(
    job_id: str,
    audio_path: str,
    video_path: str,
    provider: Optional[str],
    preset: str,
) -> None:
    """Background worker: generate one lip-sync video and record the outcome."""
    from .lipsync import generate_lipsync_video

    entry = _lipsync_jobs.get(job_id)
    if entry is None:
        _safe_unlink(audio_path)
        _safe_unlink(video_path)
        return

    tmp_output: Optional[str] = None
    try:
        with _lipsync_gpu_lock:
            with _lipsync_jobs_lock:
                if entry.get("cancelled"):
                    entry["status"] = "cancelled"
                    return
                entry["status"] = "running"
                entry["started_at"] = time.monotonic()

            _release_tts_backend_for_gpu_phase("lip-sync")

            fd_o, tmp_output = tempfile.mkstemp(suffix=".mp4")
            os.close(fd_o)
            generate_lipsync_video(
                audio_path=audio_path,
                reference_video_path=video_path,
                output_path=tmp_output,
                provider=provider or _lipsync_provider_name,
                device=_device,
                latentsync_preset=preset,
            )

        with _lipsync_jobs_lock:
            entry["finished_at"] = time.monotonic()
            if entry.get("cancelled"):
                entry["status"] = "cancelled"
                _safe_unlink(tmp_output)
            else:
                entry["status"] = "done"
                entry["output_path"] = tmp_output
    except Exception as exc:  # noqa: BLE001 — surface any failure to the client
        with _lipsync_jobs_lock:
            entry["status"] = "failed"
            entry["error"] = str(exc)
            entry["finished_at"] = time.monotonic()
        _safe_unlink(tmp_output)
    finally:
        _safe_unlink(audio_path)
        _safe_unlink(video_path)


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
            "capabilities": ["synthesize", "transcribe", "align", "lipsync"],
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

    @app.post("/synthesize")
    async def synthesize(request: Request):
        """Synthesize text to audio.

        Accepts either application/json (``{text, language}``) or
        multipart/form-data with optional ``ref_audio`` (file) and
        ``ref_text`` (string) fields for per-request voice cloning.

        Requests are submitted to the ``BatchingSynthesizer`` and coalesced
        into a single batched forward pass on the model when multiple
        concurrent requests share the same reference voice.
        """
        if _backend is None or _batcher is None:
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
            ref_audio_suffix: Optional[str] = None
            if ref_audio_field is not None and hasattr(ref_audio_field, "read"):
                ref_audio_bytes = await ref_audio_field.read()
                ref_audio_filename = getattr(ref_audio_field, "filename", None)
                ref_audio_suffix = os.path.splitext(ref_audio_filename or "ref.wav")[1] or ".wav"
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
            ref_audio_suffix = None

        fut = _batcher.submit(
            text=text,
            language=language,
            ref_audio_bytes=ref_audio_bytes,
            ref_audio_suffix=ref_audio_suffix,
            ref_text=ref_text,
        )
        audio_bytes = await asyncio.wrap_future(fut)
        return Response(content=audio_bytes, media_type=_media_type_for(_backend.output_format))

    # ------------------------------------------------------------------
    # Transcription (audio → text)
    # ------------------------------------------------------------------

    @app.post("/transcribe")
    async def transcribe(
        audio: UploadFile = File(...),
        language: str = Form("en-US"),
    ):
        """Transcribe *audio* and return the plain text.

        Used by the web backend to auto-fill ``ref_text`` for
        voice-cloning reference clips so Qwen3-TTS can run in ICL mode.
        """
        from .transcription import transcribe_audio

        suffix = os.path.splitext(audio.filename or "audio.wav")[1] or ".wav"
        fd, tmp_audio = tempfile.mkstemp(suffix=suffix)
        os.close(fd)

        try:
            content = await audio.read()
            with open(tmp_audio, "wb") as f:
                f.write(content)

            with _lipsync_gpu_lock:
                _release_tts_backend_for_gpu_phase("transcription")
                try:
                    text = transcribe_audio(tmp_audio, language=language, device=_device)
                finally:
                    from .gpu_memory import release_torch_cuda_cache

                    release_torch_cuda_cache()
            return {"text": text}
        finally:
            if os.path.exists(tmp_audio):
                os.unlink(tmp_audio)

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

            with _lipsync_gpu_lock:
                _release_tts_backend_for_gpu_phase("alignment")
                try:
                    words = align_chunk(
                        tmp_audio,
                        text,
                        provider=provider or _aligner_name,
                        language=language,
                        device=_device,
                    )
                finally:
                    from .gpu_memory import release_torch_cuda_cache

                    release_torch_cuda_cache()

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
    async def lipsync_submit(
        audio: UploadFile = File(...),
        reference_video: UploadFile = File(...),
        provider: Optional[str] = Form(None),
        latentsync_preset: str = Form("quality"),
    ):
        """Queue a lip-sync job and return a handle to poll.

        Generation runs in a background thread, so this returns immediately —
        the client polls ``GET /lipsync/{id}`` and never holds a long-lived
        connection open while the GPU works.
        """
        audio_suffix = os.path.splitext(audio.filename or "audio.wav")[1] or ".wav"
        video_suffix = os.path.splitext(reference_video.filename or "ref.mp4")[1] or ".mp4"

        fd_a, tmp_audio = tempfile.mkstemp(suffix=audio_suffix)
        os.close(fd_a)
        fd_v, tmp_video = tempfile.mkstemp(suffix=video_suffix)
        os.close(fd_v)
        with open(tmp_audio, "wb") as f:
            f.write(await audio.read())
        with open(tmp_video, "wb") as f:
            f.write(await reference_video.read())

        job_id = uuid.uuid4().hex
        with _lipsync_jobs_lock:
            _lipsync_jobs[job_id] = {
                "status": "queued",
                "error": None,
                "output_path": None,
                "cancelled": False,
                "submitted_at": time.monotonic(),
                "started_at": None,
                "finished_at": None,
            }
        threading.Thread(
            target=_run_lipsync_job,
            args=(job_id, tmp_audio, tmp_video, provider, latentsync_preset),
            daemon=True,
        ).start()
        return {"lipsync_id": job_id, "status": "queued"}

    @app.get("/lipsync/{job_id}")
    def lipsync_status(job_id: str):
        """Report a lip-sync job's status and elapsed generation time."""
        with _lipsync_jobs_lock:
            entry = _lipsync_jobs.get(job_id)
            if entry is None:
                raise HTTPException(404, "Unknown lip-sync job")
            started = entry.get("started_at")
            finished = entry.get("finished_at")
            elapsed = 0.0 if started is None else (finished or time.monotonic()) - started
            return {
                "lipsync_id": job_id,
                "status": entry["status"],
                "elapsed": round(elapsed, 1),
                "error": entry.get("error"),
            }

    @app.get("/lipsync/{job_id}/result")
    def lipsync_result(job_id: str):
        """Download the finished lip-synced video."""
        with _lipsync_jobs_lock:
            entry = _lipsync_jobs.get(job_id)
            if entry is None:
                raise HTTPException(404, "Unknown lip-sync job")
            if entry["status"] != "done" or not entry.get("output_path"):
                raise HTTPException(409, f"Lip-sync job is {entry['status']}")
            output_path = entry["output_path"]
        with open(output_path, "rb") as f:
            return Response(content=f.read(), media_type="video/mp4")

    @app.post("/lipsync/{job_id}/cancel")
    def lipsync_cancel(job_id: str):
        """Request cancellation; an in-flight job's result is discarded."""
        with _lipsync_jobs_lock:
            entry = _lipsync_jobs.get(job_id)
            if entry is None:
                raise HTTPException(404, "Unknown lip-sync job")
            entry["cancelled"] = True
            if entry["status"] == "queued":
                entry["status"] = "cancelled"
            return {"lipsync_id": job_id, "status": entry["status"]}

    @app.delete("/lipsync/{job_id}")
    def lipsync_delete(job_id: str):
        """Discard a lip-sync job record and its output file."""
        with _lipsync_jobs_lock:
            entry = _lipsync_jobs.pop(job_id, None)
        if entry:
            _safe_unlink(entry.get("output_path"))
        return {"detail": "deleted"}

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
    p.add_argument(
        "--max-batch",
        type=int,
        default=8,
        help=(
            "Maximum number of /synthesize requests coalesced into a single "
            "batched model call (default: 8). Raise to saturate the GPU on "
            "small models like Qwen3-TTS 0.6B; 8 is safe on an L4."
        ),
    )
    p.add_argument(
        "--batch-window-ms",
        type=int,
        default=30,
        help=(
            "Milliseconds the batcher waits for additional concurrent "
            "requests to fill a partial batch (default: 30). Set to 0 to "
            "disable coalescing and run requests as they arrive."
        ),
    )
    register_backend_args(p, context="server")
    return p


def main(argv=None):
    global _backend, _batcher, _backend_name, _device, _aligner_name, _lipsync_provider_name

    from .logging_config import setup_logging
    setup_logging("inference_server")

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

    if not hasattr(_backend, "synthesize_batch"):
        print(
            f"ERROR: backend '{_backend_name}' does not implement synthesize_batch; "
            "the inference server requires a batch-capable backend.",
            file=sys.stderr,
        )
        sys.exit(1)

    from .inference_batcher import BatchingSynthesizer

    _batcher = BatchingSynthesizer(
        backend=_backend,
        max_batch=args.max_batch,
        batch_window_ms=args.batch_window_ms,
        run_lock=_lipsync_gpu_lock,
    )
    _batcher.start()

    print(
        f"Backend ready. Serving on {args.host}:{args.port} "
        f"(max_batch={args.max_batch}, batch_window_ms={args.batch_window_ms})"
    )
    print("Capabilities: TTS synthesis, alignment, lip-sync generation")

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
