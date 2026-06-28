"""Remote TTS backend — delegates synthesis to an inference server over HTTP.

Used on the CPU VM to offload TTS to a GPU VM running ``screencastgen-server``.
"""

from typing import Optional

from .base import BackendArg, BackendSpec


class RemoteTTS:
    """TTSBackend that calls a remote screencastgen inference server."""

    def __init__(
        self,
        server_url: str = "http://localhost:8100",
        language: str = "en-US",
        timeout: int = 43200,
        ref_audio_path: Optional[str] = None,
        ref_text: Optional[str] = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.language = language
        self.timeout = timeout
        self.ref_audio_path = ref_audio_path
        self.ref_text = ref_text
        self._server_format: Optional[str] = None
        self._server_max_bytes: Optional[int] = None
        self._ref_audio_bytes: Optional[bytes] = None
        if ref_audio_path:
            try:
                with open(ref_audio_path, "rb") as f:
                    self._ref_audio_bytes = f.read()
            except OSError as exc:
                print(f"  Warning: could not read ref audio {ref_audio_path}: {exc}")
                self._ref_audio_bytes = None
        self._fetch_server_info()

    def _fetch_server_info(self):
        """Query /health to learn the remote backend's capabilities."""
        import json
        import urllib.request

        try:
            req = urllib.request.Request(f"{self.server_url}/health")
            with urllib.request.urlopen(req, timeout=10) as resp:
                info = json.loads(resp.read())
            self._server_format = info.get("output_format", "wav")
            self._server_max_bytes = info.get("max_chunk_bytes", 20000)
            print(
                f"  Connected to TTS server: backend={info.get('backend')}, "
                f"format={self._server_format}, max_chunk_bytes={self._server_max_bytes}"
            )
        except Exception as exc:
            print(f"  Warning: could not reach TTS server at {self.server_url}: {exc}")
            print("  Using defaults (wav, 20000 bytes). Server must be up before synthesis starts.")
            self._server_format = "wav"
            self._server_max_bytes = 20000

    @property
    def max_chunk_bytes(self) -> int:
        return self._server_max_bytes or 20000

    @property
    def output_format(self) -> str:
        return self._server_format or "wav"

    def synthesize(self, text: str, output_path: str) -> None:
        """Send *text* to the inference server and save the audio to *output_path*."""
        import json
        import os
        import time
        import urllib.request

        url = f"{self.server_url}/synthesize"

        if self._ref_audio_bytes:
            # Multipart with per-request reference voice override.
            boundary = "----ScreencastgenRemoteTTSBoundary"
            parts: list[bytes] = []

            def add_field(name: str, value: str) -> None:
                parts.append(
                    (
                        f"--{boundary}\r\n"
                        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                        f"{value}\r\n"
                    ).encode("utf-8")
                )

            add_field("text", text)
            add_field("language", self.language)
            if self.ref_text:
                add_field("ref_text", self.ref_text)

            ref_filename = (
                os.path.basename(self.ref_audio_path) if self.ref_audio_path else "ref.wav"
            )
            parts.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="ref_audio"; filename="{ref_filename}"\r\n'
                    f"Content-Type: audio/wav\r\n\r\n"
                ).encode("utf-8")
            )
            parts.append(self._ref_audio_bytes)
            parts.append(b"\r\n")
            parts.append(f"--{boundary}--\r\n".encode("utf-8"))

            body = b"".join(parts)
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
        else:
            payload = json.dumps(
                {
                    "text": text,
                    "language": self.language,
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                audio_bytes = resp.read()
        except Exception as exc:
            elapsed = time.monotonic() - started
            raise RuntimeError(
                f"TTS server request failed ({self.server_url}) after {elapsed:.1f}s "
                f"(timeout={self.timeout}s): {exc}"
            ) from exc

        if not audio_bytes:
            raise RuntimeError("TTS server returned empty audio")

        with open(output_path, "wb") as f:
            f.write(audio_bytes)


def _build_kwargs(args, invocation: str):
    return {
        "server_url": getattr(args, "tts_server_url", "http://localhost:8100"),
        "language": getattr(args, "language", "en-US"),
        "timeout": getattr(args, "tts_timeout", 43200),
        "ref_audio_path": getattr(args, "ref_audio", None),
        "ref_text": getattr(args, "ref_text", None),
    }


SPEC = BackendSpec(
    name="remote",
    module_path=__name__,
    class_name="RemoteTTS",
    contexts=frozenset({"cli"}),
    capabilities=frozenset({"remote", "server_managed_reference"}),
    extra_args=(
        BackendArg(
            ("--tts-server-url",),
            {
                "default": "http://localhost:8100",
                "help": (
                    "URL of the GPU inference server "
                    "(for --backend remote, default: http://localhost:8100)"
                ),
            },
            contexts=frozenset({"cli"}),
        ),
    ),
    build_kwargs=_build_kwargs,
)
