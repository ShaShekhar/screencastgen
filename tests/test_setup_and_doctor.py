"""Tests for cross-platform setup profiles and environment diagnostics."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

from screencastgen import cli
from screencastgen.doctor import CheckResult, _remote_server, resolve_profile, run_doctor


BASE_COMMANDS = ("git", "uv", "node", "npm", "ffmpeg", "ffprobe")
LOCAL_GPU_COMMANDS = BASE_COMMANDS + ("gcc", "g++", "make", "nvidia-smi", "bash")


def _load_setup_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "setup.py"
    spec = importlib.util.spec_from_file_location("screencastgen_setup", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _available(commands: tuple[str, ...]) -> dict[str, str]:
    return {name: f"/bin/{name}" for name in commands}


def test_doctor_auto_selects_local_gpu_on_linux_with_nvidia():
    with patch("screencastgen.doctor.platform.system", return_value="Linux"), patch(
        "screencastgen.doctor.nvidia_available", return_value=True
    ):
        assert resolve_profile("auto") == "local-gpu"


def test_doctor_auto_selects_remote_client_on_macos():
    with patch("screencastgen.doctor.platform.system", return_value="Darwin"):
        assert resolve_profile("auto") == "remote-client"


def test_doctor_returns_nonzero_for_required_failure():
    emitted = []
    with patch(
        "screencastgen.doctor.collect_checks",
        return_value=[CheckResult("FAIL", "ffmpeg", "not found")],
    ):
        assert run_doctor(emit=emitted.append) == 1
    assert any("[FAIL] ffmpeg" in line for line in emitted)


def test_doctor_allows_warnings():
    with patch(
        "screencastgen.doctor.collect_checks",
        return_value=[CheckResult("WARN", "remote GPU server", "not checked")],
    ):
        assert run_doctor(emit=lambda line: None) == 0


def test_remote_doctor_validates_server_capabilities():
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                {
                    "status": "ok",
                    "backend": "qwen",
                    "device": "cuda",
                    "capabilities": ["synthesize", "transcribe", "align", "lipsync"],
                }
            ).encode()

    with patch("screencastgen.doctor.urllib.request.urlopen", return_value=Response()):
        result = _remote_server("http://gpu.example")
    assert result.level == "OK"
    assert "qwen" in result.detail


def test_download_command_propagates_failure():
    class Args:
        pass

    with patch(
        "screencastgen.models.download_selected_models",
        side_effect=RuntimeError("download failed"),
    ):
        assert cli.run_download_models(Args()) == 1


def test_setup_auto_profile_matches_platform_capability():
    setup = _load_setup_module()
    with patch.object(setup.platform, "system", return_value="Linux"), patch.object(
        setup, "has_nvidia", return_value=True
    ):
        assert setup.resolve_profile("auto") == "local-gpu"
    with patch.object(setup.platform, "system", return_value="Windows"):
        assert setup.resolve_profile("auto") == "remote-client"


def test_setup_check_does_not_install():
    setup = _load_setup_module()
    with patch.object(setup, "resolve_profile", return_value="dev"), patch.object(
        setup, "preflight", return_value=True
    ), patch.object(setup, "install") as install:
        assert setup.main(["--check"]) == 0
    install.assert_not_called()


def test_setup_preflight_prints_debian_prerequisite_commands(capsys):
    setup = _load_setup_module()
    with patch.object(setup.platform, "system", return_value="Linux"), patch.object(
        setup.shutil, "which", return_value=None
    ), patch.object(setup.Path, "read_text", return_value="ID=ubuntu"):
        assert setup.preflight("dev") is False

    output = capsys.readouterr().out
    assert "sudo apt-get update" in output
    assert (
        "sudo apt-get install -y curl ca-certificates git ffmpeg "
        "build-essential python3.10-dev"
    ) in output
    assert "curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -" in output
    assert "sudo apt-get install -y nodejs" in output
    assert "curl -LsSf https://astral.sh/uv/install.sh | sh" in output
    assert (
        "uv installation: https://docs.astral.sh/uv/getting-started/installation/"
        in output
    )


def test_setup_preflight_local_gpu_hint_mentions_build_essential(capsys):
    setup = _load_setup_module()
    available = _available(BASE_COMMANDS + ("bash",))
    with patch.object(setup.platform, "system", return_value="Linux"), patch.object(
        setup.shutil, "which", side_effect=lambda name: available.get(name)
    ), patch.object(setup.Path, "read_text", return_value="ID=ubuntu"):
        assert setup.preflight("local-gpu") is False

    output = capsys.readouterr().out
    assert "missing required commands: gcc, g++, make, nvidia-smi" in output
    assert "build-essential provides gcc, g++, and make" in output


def test_native_windows_rejects_local_gpu_profile():
    setup = _load_setup_module()
    available = _available(LOCAL_GPU_COMMANDS)
    with patch.object(setup.platform, "system", return_value="Windows"), patch.object(
        setup.shutil, "which", side_effect=lambda name: available.get(name)
    ):
        assert setup.preflight("local-gpu") is False
