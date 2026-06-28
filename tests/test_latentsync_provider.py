"""Tests for the LatentSync sidecar provider integration."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

from screencastgen.providers.lipsync.latentsync_provider import (
    LatentSyncRuntimeSpec,
    PRESETS,
    LatentSyncSession,
    _SESSIONS,
    _close_all_sessions,
    _get_inference_timeout_seconds,
    close_idle_latentsync_sessions,
    download_latentsync_checkpoints,
    find_latentsync_python,
    find_latentsync_root,
)


def _make_latentsync_root(path) -> str:
    (path / "latentsync").mkdir(parents=True)
    (path / "configs").mkdir()
    (path / "checkpoints").mkdir()
    return str(path)


def _make_executable(path) -> str:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return str(path)


class _FakeStdout:
    def __init__(self, messages):
        self._messages = [json.dumps(message) + "\n" for message in messages]
        self._r, self._w = os.pipe()

    def readline(self):
        if self._messages:
            return self._messages.pop(0)
        return ""

    def fileno(self):
        # Write a byte so select() sees this fd as ready immediately
        os.write(self._w, b"x")
        return self._r


class _FakeStderr:
    """Iterable stderr that yields nothing."""

    def __iter__(self):
        return iter([])


class _FakeStdin:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)

    def flush(self):
        return None


class _FakeProcess:
    def __init__(self, messages):
        self.stdout = _FakeStdout(messages)
        self.stderr = _FakeStderr()
        self.stdin = _FakeStdin()
        self._returncode = None

    def poll(self):
        return self._returncode

    def wait(self, timeout=None):
        self._returncode = 0
        return 0

    def terminate(self):
        self._returncode = -15

    def kill(self):
        self._returncode = -9


def test_find_latentsync_root_uses_env(monkeypatch, tmp_path):
    root = _make_latentsync_root(tmp_path / "LatentSync")
    monkeypatch.setenv("LATENTSYNC_ROOT", root)

    assert find_latentsync_root() == root


def test_find_latentsync_python_uses_env(monkeypatch, tmp_path):
    python_path = _make_executable(tmp_path / "python")
    monkeypatch.setenv("LATENTSYNC_PYTHON", python_path)

    assert find_latentsync_python() == python_path


def test_download_latentsync_checkpoints_uses_sidecar_python(tmp_path):
    root = _make_latentsync_root(tmp_path / "LatentSync")
    python_path = _make_executable(tmp_path / "python")

    with patch("screencastgen.providers.lipsync.latentsync_provider.subprocess.run") as mock_run:
        download_latentsync_checkpoints(
            root=root,
            python_executable=python_path,
            hf_repo="ByteDance/LatentSync-1.6",
            checkpoint_file="latentsync_unet.pt",
            audio_checkpoint="whisper/tiny.pt",
        )

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == python_path
    assert cmd[2] == "download-checkpoints"
    assert "--local-dir" in cmd
    assert os.path.join(root, "checkpoints") in cmd


def test_latentsync_session_sends_json_requests(tmp_path):
    root = _make_latentsync_root(tmp_path / "LatentSync")
    python_path = _make_executable(tmp_path / "python")
    config_path = tmp_path / "stage2_512.yaml"
    config_path.write_text("dummy", encoding="utf-8")
    checkpoint_path = tmp_path / "latentsync_unet.pt"
    checkpoint_path.write_text("dummy", encoding="utf-8")
    output_path = tmp_path / "output.mp4"
    output_path.write_text("video", encoding="utf-8")

    spec = LatentSyncRuntimeSpec(
        root=root,
        python_executable=python_path,
        device="cuda",
        preset=PRESETS["quality"],
        config_path=str(config_path),
        checkpoint_path=str(checkpoint_path),
        temp_dir=str(tmp_path / "temp"),
    )
    fake_process = _FakeProcess(
        [
            {"ok": True, "event": "ready"},
            {"ok": True, "output_path": str(output_path)},
        ]
    )

    with patch("screencastgen.providers.lipsync.latentsync_provider.subprocess.Popen", return_value=fake_process):
        session = LatentSyncSession(spec)
        result = session.run("input.mp4", "input.wav", str(output_path))

    assert result == str(output_path)
    request = json.loads(fake_process.stdin.writes[0])
    assert request == {
        "cmd": "run",
        "video_path": "input.mp4",
        "audio_path": "input.wav",
        "output_path": str(output_path),
    }


def test_close_idle_latentsync_sessions_closes_cached_worker(tmp_path):
    root = _make_latentsync_root(tmp_path / "LatentSync")
    python_path = _make_executable(tmp_path / "python")
    config_path = tmp_path / "stage2_512.yaml"
    config_path.write_text("dummy", encoding="utf-8")
    checkpoint_path = tmp_path / "latentsync_unet.pt"
    checkpoint_path.write_text("dummy", encoding="utf-8")

    spec = LatentSyncRuntimeSpec(
        root=root,
        python_executable=python_path,
        device="cuda",
        preset=PRESETS["quality"],
        config_path=str(config_path),
        checkpoint_path=str(checkpoint_path),
        temp_dir=str(tmp_path / "temp"),
    )
    fake_process = _FakeProcess([{"ok": True, "event": "ready"}])

    _close_all_sessions()
    with patch("screencastgen.providers.lipsync.latentsync_provider.subprocess.Popen", return_value=fake_process):
        session = LatentSyncSession(spec)

    cache_key = (root, python_path, "cuda", "quality", str(checkpoint_path))
    _SESSIONS[cache_key] = session
    session._last_used_at = 0.0

    assert close_idle_latentsync_sessions(idle_seconds=0.001) == 1
    assert cache_key not in _SESSIONS
    assert fake_process.poll() == 0
    shutdown = json.loads(fake_process.stdin.writes[-1])
    assert shutdown == {"cmd": "shutdown"}


def test_latentsync_inference_timeout_uses_env(monkeypatch):
    monkeypatch.setenv("LATENTSYNC_INFERENCE_TIMEOUT_SECONDS", "1800")

    assert _get_inference_timeout_seconds() == 1800
