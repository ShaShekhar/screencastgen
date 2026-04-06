"""Remote TTS backend — delegates synthesis to an inference server over HTTP.

Used on the CPU VM to offload TTS to a GPU VM running ``screencastgen-server``.
"""

from typing import Optional


class RemoteTTS:
    """TTSBackend that calls a remote screencastgen inference server."""

    def __init__(
        self,
        server_url: str = "http://localhost:8100",
        language: str = "en-US",
        timeout: int = 300,
    ):
        self.server_url = server_url.rstrip("/")
        self.language = language
        self.timeout = timeout

        # Fetch backend metadata from the server
        self._server_format: Optional[str] = None
        self._server_max_bytes: Optional[int] = None
        self._fetch_server_info()

    def _fetch_server_info(self):
        """Query /health to learn the remote backend's capabilities."""
        import urllib.request
        import json

        try:
            req = urllib.request.Request(f"{self.server_url}/health")
            with urllib.request.urlopen(req, timeout=10) as resp:
                info = json.loads(resp.read())
            self._server_format = info.get("output_format", "wav")
            self._server_max_bytes = info.get("max_chunk_bytes", 20000)
            print(f"  Connected to TTS server: backend={info.get('backend')}, "
                  f"format={self._server_format}, max_chunk_bytes={self._server_max_bytes}")
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
        import urllib.request
        import json

        payload = json.dumps({
            "text": text,
            "language": self.language,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.server_url}/synthesize",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                audio_bytes = resp.read()
        except Exception as exc:
            raise RuntimeError(
                f"TTS server request failed ({self.server_url}): {exc}"
            ) from exc

        if not audio_bytes:
            raise RuntimeError("TTS server returned empty audio")

        with open(output_path, "wb") as f:
            f.write(audio_bytes)
