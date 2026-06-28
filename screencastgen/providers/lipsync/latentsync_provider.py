"""LatentSync lip-sync provider."""

from __future__ import annotations

import atexit
import json
import logging
import os
import select
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LatentSyncPreset:
    """Runtime settings for a LatentSync inference preset."""

    name: str
    config_candidates: Tuple[Tuple[str, ...], ...]
    checkpoint_candidates: Tuple[str, ...]
    guidance_scale: float
    inference_steps: int
    seed: int = 1247
    enable_deepcache: bool = True


# Default timeout (seconds) for waiting on a worker response.  Startup loads
# models onto GPU so it gets a longer window; inference is per-chunk.
_STARTUP_TIMEOUT = 300  # 5 minutes — model loading can be slow
_INFERENCE_TIMEOUT = 600  # 10 minutes — long clips on slow GPUs
_DEFAULT_IDLE_TIMEOUT_SECONDS = 60.0


PRESETS: Dict[str, LatentSyncPreset] = {
    "small": LatentSyncPreset(
        name="small",
        config_candidates=(
            ("configs", "unet", "stage2.yaml"),
            ("configs", "unet", "stage2_256.yaml"),
        ),
        checkpoint_candidates=(
            "LATENTSYNC_SMALL_CKPT",
            "LATENTSYNC_CKPT",
            "checkpoints/latentsync_unet_1_5.pt",
            "checkpoints/latentsync_unet_256.pt",
            "checkpoints/latentsync_unet_small.pt",
            "checkpoints/latentsync_unet.pt",
        ),
        guidance_scale=1.0,
        inference_steps=20,
    ),
    "quality": LatentSyncPreset(
        name="quality",
        config_candidates=(
            ("configs", "unet", "stage2_512.yaml"),
            ("configs", "unet", "stage2.yaml"),
        ),
        checkpoint_candidates=(
            "LATENTSYNC_QUALITY_CKPT",
            "LATENTSYNC_CKPT",
            "checkpoints/latentsync_unet_1_6.pt",
            "checkpoints/latentsync_unet_512.pt",
            "checkpoints/latentsync_unet.pt",
        ),
        guidance_scale=1.5,
        inference_steps=20,
    ),
}

_SESSIONS: Dict[Tuple[str, str, str, str, str], "LatentSyncSession"] = {}
_SESSION_LOCK = threading.Lock()
_IDLE_CLEANUP_TIMER: threading.Timer | None = None


def _project_root() -> str:
    return os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__)),
            ),
        ),
    )


def _worker_script_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "latentsync_worker.py")


def _is_executable_file(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


def _looks_like_latentsync_root(path: str) -> bool:
    return (
        os.path.isdir(path)
        and os.path.isdir(os.path.join(path, "latentsync"))
        and os.path.isdir(os.path.join(path, "configs"))
    )


def _resolve_latentsync_root(path: str | None = None) -> str:
    if path:
        resolved = os.path.abspath(os.path.expanduser(path))
        if _looks_like_latentsync_root(resolved):
            return resolved
        raise ImportError(
            f"LatentSync root not found at {resolved}\n"
            "Expected a clone of https://github.com/bytedance/LatentSync with "
            "`latentsync/` and `configs/` directories."
        )

    env = os.environ.get("LATENTSYNC_ROOT")
    if env:
        return _resolve_latentsync_root(env)

    repo_root = _project_root()
    candidates = (
        os.path.join(repo_root, "external", "LatentSync"),
        os.path.join(repo_root, "LatentSync"),
    )
    for candidate in candidates:
        if _looks_like_latentsync_root(candidate):
            return candidate

    raise ImportError(
        "LatentSync repo not found.\n"
        "Set LATENTSYNC_ROOT=/path/to/LatentSync or run scripts/install_latentsync.sh."
    )


def find_latentsync_root() -> str:
    """Locate the LatentSync repo directory."""
    return _resolve_latentsync_root()


def _resolve_latentsync_python(path: str | None = None) -> str:
    if path:
        resolved = os.path.abspath(os.path.expanduser(path))
        if _is_executable_file(resolved):
            return resolved
        raise ImportError(
            f"LatentSync Python interpreter not found at {resolved}\n"
            "Set LATENTSYNC_PYTHON to the Python inside the dedicated LatentSync env."
        )

    env = os.environ.get("LATENTSYNC_PYTHON")
    if env:
        return _resolve_latentsync_python(env)

    repo_root = _project_root()
    candidates = (
        os.path.join(repo_root, ".venvs", "latentsync", "bin", "python"),
        os.path.join(repo_root, "external", "LatentSync", ".venv", "bin", "python"),
    )
    for candidate in candidates:
        if _is_executable_file(candidate):
            return candidate

    raise ImportError(
        "LatentSync Python interpreter not found.\n"
        "Set LATENTSYNC_PYTHON=/path/to/.venvs/latentsync/bin/python or run "
        "scripts/install_latentsync.sh."
    )


def find_latentsync_python() -> str:
    """Locate the Python interpreter for the dedicated LatentSync env."""
    return _resolve_latentsync_python()


def _resolve_preset(name: str) -> LatentSyncPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown LatentSync preset {name!r}. Choose from: {', '.join(PRESETS)}") from exc


def _resolve_config_path(root: str, preset: LatentSyncPreset) -> str:
    tried = []
    for parts in preset.config_candidates:
        path = os.path.join(root, *parts)
        if os.path.isfile(path):
            return path
        tried.append(path)

    raise FileNotFoundError(
        f"LatentSync config not found for preset '{preset.name}'.\n"
        "Looked for:\n"
        + "\n".join(f"  - {p}" for p in tried)
        + "\nEnsure LATENTSYNC_ROOT is set correctly or reinstall LatentSync."
    )


def _resolve_checkpoint_path(root: str, preset: LatentSyncPreset) -> str:
    for candidate in preset.checkpoint_candidates:
        if candidate.startswith("LATENTSYNC_"):
            path = os.environ.get(candidate)
        else:
            path = os.path.join(root, candidate)
        if path and os.path.isfile(path):
            return path

    raise FileNotFoundError(
        f"LatentSync checkpoint not found for preset '{preset.name}'.\n"
        "Looked for one of:\n"
        + "\n".join(f"  - {candidate}" for candidate in preset.checkpoint_candidates)
        + "\nDownload it with:\n"
        + "  python -m screencastgen download-models --package latentsync\n"
        + "Or see: https://github.com/bytedance/LatentSync#download-checkpoints"
    )


@dataclass(frozen=True)
class LatentSyncRuntimeSpec:
    """Fully resolved runtime inputs for a reusable LatentSync worker session."""

    root: str
    python_executable: str
    device: str
    preset: LatentSyncPreset
    config_path: str
    checkpoint_path: str
    temp_dir: str


def _forward_stderr(stream, preset_name: str) -> None:
    """Read stderr from the worker and forward lines to the logger."""
    try:
        for line in stream:
            stripped = line.rstrip("\n")
            if stripped:
                logger.info("[LatentSync/%s] %s", preset_name, stripped)
    except (ValueError, OSError):
        # Stream closed
        pass


class LatentSyncSession:
    """Reusable LatentSync subprocess session running in a separate Python env."""

    def __init__(self, spec: LatentSyncRuntimeSpec):
        self.spec = spec
        self._run_lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._stderr_thread: threading.Thread | None = None
        self._last_used_at = time.monotonic()
        self._start()

    def _command(self) -> list[str]:
        cmd = [
            self.spec.python_executable,
            _worker_script_path(),
            "serve",
            "--root",
            self.spec.root,
            "--config-path",
            self.spec.config_path,
            "--checkpoint-path",
            self.spec.checkpoint_path,
            "--temp-dir",
            self.spec.temp_dir,
            "--device",
            self.spec.device,
            "--inference-steps",
            str(self.spec.preset.inference_steps),
            "--guidance-scale",
            str(self.spec.preset.guidance_scale),
            "--seed",
            str(self.spec.preset.seed),
        ]
        if self.spec.preset.enable_deepcache:
            cmd.append("--enable-deepcache")
        return cmd

    def _start(self) -> None:
        if self.spec.device != "cuda":
            raise RuntimeError("LatentSync inference requires CUDA. Use a GPU device or the remote GPU server.")

        os.makedirs(self.spec.temp_dir, exist_ok=True)

        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")

        self._process = subprocess.Popen(
            self._command(),
            cwd=self.spec.root,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._stderr_thread = threading.Thread(
            target=_forward_stderr,
            args=(self._process.stderr, self.spec.preset.name),
            daemon=True,
        )
        self._stderr_thread.start()

        message = self._read_message(context="startup", timeout=_STARTUP_TIMEOUT)
        if not message.get("ok"):
            self.close()
            raise RuntimeError(message.get("error", "LatentSync worker failed to start"))
        if message.get("event") != "ready":
            self.close()
            raise RuntimeError(f"Unexpected LatentSync worker response: {message}")

    def _read_message(self, *, context: str, timeout: int | None = None) -> dict:
        process = self._process
        if process is None or process.stdout is None:
            raise RuntimeError("LatentSync worker is not running")

        if timeout is not None:
            fd = process.stdout.fileno()
            ready, _, _ = select.select([fd], [], [], timeout)
            if not ready:
                self.close()
                raise RuntimeError(
                    f"LatentSync worker timed out after {timeout}s during {context}. "
                    "The GPU may be out of memory or the input too large."
                )

        line = process.stdout.readline()
        if not line:
            code = process.poll()
            raise RuntimeError(f"LatentSync worker exited unexpectedly during {context} (exit code: {code})")

        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"LatentSync worker returned invalid {context} response: {line.strip()}"
            ) from exc

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return

        try:
            if process.poll() is None and process.stdin is not None:
                process.stdin.write(json.dumps({"cmd": "shutdown"}) + "\n")
                process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def close_if_idle(self, cutoff: float) -> bool:
        if self._last_used_at > cutoff:
            return False
        if not self._run_lock.acquire(blocking=False):
            return False
        try:
            if self._last_used_at > cutoff:
                return False
            self.close()
            return True
        finally:
            self._run_lock.release()

    def run(self, video_path: str, audio_path: str, output_path: str) -> str:
        """Generate one lip-sync clip using the loaded LatentSync worker."""
        try:
            with self._run_lock:
                if self._process is None or self._process.poll() is not None:
                    self._start()

                process = self._process
                if process is None or process.stdin is None:
                    raise RuntimeError("LatentSync worker is not running")

                request = {
                    "cmd": "run",
                    "video_path": video_path,
                    "audio_path": audio_path,
                    "output_path": output_path,
                }
                process.stdin.write(json.dumps(request) + "\n")
                process.stdin.flush()

                message = self._read_message(context="inference", timeout=_INFERENCE_TIMEOUT)
                if not message.get("ok"):
                    raise RuntimeError(message.get("error", "LatentSync worker failed"))
        finally:
            self._last_used_at = time.monotonic()
            _schedule_idle_cleanup()

        if not os.path.isfile(output_path):
            raise RuntimeError(f"LatentSync completed but output file not found at {output_path}")
        return output_path


def _close_all_sessions() -> None:
    global _IDLE_CLEANUP_TIMER
    with _SESSION_LOCK:
        if _IDLE_CLEANUP_TIMER is not None:
            _IDLE_CLEANUP_TIMER.cancel()
            _IDLE_CLEANUP_TIMER = None
        sessions = list(_SESSIONS.values())
        _SESSIONS.clear()
    for session in sessions:
        session.close()


atexit.register(_close_all_sessions)


def _get_idle_timeout_seconds() -> float | None:
    raw = os.environ.get("LATENTSYNC_IDLE_TIMEOUT_SECONDS")
    if raw is None:
        return _DEFAULT_IDLE_TIMEOUT_SECONDS

    value = raw.strip().lower()
    if value in {"", "0", "none", "off", "false", "disabled"}:
        return None
    try:
        timeout = float(value)
    except ValueError:
        logger.warning(
            "Ignoring invalid LATENTSYNC_IDLE_TIMEOUT_SECONDS=%r; using %.0fs",
            raw,
            _DEFAULT_IDLE_TIMEOUT_SECONDS,
        )
        return _DEFAULT_IDLE_TIMEOUT_SECONDS
    if timeout <= 0:
        return None
    return timeout


def close_idle_latentsync_sessions(idle_seconds: float | None = None) -> int:
    """Close cached LatentSync workers that have been idle long enough."""
    timeout = _get_idle_timeout_seconds() if idle_seconds is None else idle_seconds
    if timeout is None:
        return 0

    cutoff = time.monotonic() - timeout
    closed = 0
    with _SESSION_LOCK:
        for key, session in list(_SESSIONS.items()):
            if session.close_if_idle(cutoff):
                _SESSIONS.pop(key, None)
                closed += 1
    if closed:
        logger.info("Closed %s idle LatentSync worker session(s)", closed)
    return closed


def _idle_cleanup_tick() -> None:
    global _IDLE_CLEANUP_TIMER
    with _SESSION_LOCK:
        _IDLE_CLEANUP_TIMER = None
    close_idle_latentsync_sessions()
    _schedule_idle_cleanup()


def _schedule_idle_cleanup() -> None:
    global _IDLE_CLEANUP_TIMER
    timeout = _get_idle_timeout_seconds()
    if timeout is None:
        return

    with _SESSION_LOCK:
        if not _SESSIONS:
            return
        if _IDLE_CLEANUP_TIMER is not None:
            _IDLE_CLEANUP_TIMER.cancel()
        _IDLE_CLEANUP_TIMER = threading.Timer(timeout, _idle_cleanup_tick)
        _IDLE_CLEANUP_TIMER.daemon = True
        _IDLE_CLEANUP_TIMER.start()


def _build_runtime_spec(device: str, preset_name: str) -> LatentSyncRuntimeSpec:
    root = find_latentsync_root()
    python_executable = find_latentsync_python()
    preset = _resolve_preset(preset_name)
    config_path = _resolve_config_path(root, preset)

    checkpoint_path = _resolve_checkpoint_path(root, preset)
    temp_dir = os.path.join(root, "temp", preset.name)
    return LatentSyncRuntimeSpec(
        root=root,
        python_executable=python_executable,
        device=device,
        preset=preset,
        config_path=config_path,
        checkpoint_path=checkpoint_path,
        temp_dir=temp_dir,
    )


def _get_session(device: str, preset_name: str) -> LatentSyncSession:
    spec = _build_runtime_spec(device, preset_name)
    cache_key = (
        spec.root,
        spec.python_executable,
        spec.device,
        spec.preset.name,
        spec.checkpoint_path,
    )

    with _SESSION_LOCK:
        session = _SESSIONS.get(cache_key)
        if session is None:
            session = LatentSyncSession(spec)
            _SESSIONS[cache_key] = session
            needs_cleanup_timer = True
        else:
            needs_cleanup_timer = False
    if needs_cleanup_timer:
        _schedule_idle_cleanup()
    return session


def download_latentsync_checkpoints(
    *,
    root: str | None = None,
    python_executable: str | None = None,
    hf_repo: str = "ByteDance/LatentSync-1.6",
    checkpoint_file: str = "latentsync_unet.pt",
    audio_checkpoint: str = "whisper/tiny.pt",
) -> None:
    """Download the inference checkpoints using the dedicated LatentSync env."""
    resolved_root = _resolve_latentsync_root(root)
    resolved_python = _resolve_latentsync_python(python_executable)
    checkpoints_dir = os.path.join(resolved_root, "checkpoints")
    os.makedirs(checkpoints_dir, exist_ok=True)

    cmd = [
        resolved_python,
        _worker_script_path(),
        "download-checkpoints",
        "--hf-repo",
        hf_repo,
        "--local-dir",
        checkpoints_dir,
        "--checkpoint-file",
        checkpoint_file,
        "--audio-checkpoint",
        audio_checkpoint,
    ]
    subprocess.run(cmd, cwd=resolved_root, check=True)


def run_latentsync(
    video_path: str,
    audio_path: str,
    output_path: str,
    device: str,
    *,
    preset: str = "quality",
):
    """Run LatentSync lip-sync generation using a cached subprocess session."""
    session = _get_session(device, preset)
    return session.run(video_path, audio_path, output_path)
