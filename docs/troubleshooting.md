# Troubleshooting

Start with the environment doctor. It checks the selected profile without
installing packages or changing the environment.

```bash
screencastgen doctor --profile auto
```

## Local GPU is not selected

Automatic setup selects `local-gpu` only on Linux or WSL2 when `nvidia-smi` can
access an NVIDIA GPU. Native Windows, macOS, and non-GPU Linux default to the
remote-client path. Run `python3 scripts/setup.py --check` to inspect the
decision before installation.

## Remote server validation warns

Pass the server URL explicitly so the doctor can validate `/health`:

```bash
screencastgen doctor \
  --profile remote-client \
  --server-url http://gpu-vm:8100
```

## WhisperX falls back to CPU

This commonly means the expected cuDNN runtime is unavailable. Follow
[WhisperX CUDA troubleshooting](getting-started/installation.md#whisperx-cuda-troubleshooting)
to inspect the active Torch, CUDA, and cuDNN libraries.

## A pipeline resumes unexpected output

Pipelines intentionally reuse their status file and completed chunks. Pass
`--clean` to discard resumable state, or choose a different `--output-dir` and
`--status-file` for an independent run.

## More diagnostics

- [Installation guide](getting-started/installation.md)
- [Doctor reference](reference/core/doctor.md)
- [Setup script reference](reference/configuration/setup-script.md)
- [Remote GPU guide](guides/remote-gpu.md)
