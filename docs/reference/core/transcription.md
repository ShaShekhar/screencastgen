# Transcription

> WhisperX transcription helper for best-effort reference voice transcripts.

**Source:** [`screencastgen/transcription.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/transcription.py)

---

## Overview

`transcribe_audio()` turns a reference audio clip into plain text so voice-cloning backends can run with an explicit `ref_text`. It only runs Whisper transcription, not forced alignment.

Imports are deferred so lightweight CLI imports still work without WhisperX installed.

---

## Model Cache

Transcribers are cached by:

```text
(model_name, device, compute_type)
```

Each loaded model has its own lock because cached WhisperX transcriber inference is serialized for safe reuse.

---

## Device Handling

The requested device is resolved through:

1. [resolve_device()](../providers/tts-base.md)
2. [resolve_whisperx_device()](whisper-x-compat.md)

If CUDA is selected but WhisperX cannot load the expected cuDNN runtime, WhisperX falls back to CPU while the rest of the server can keep using GPU.

---

## See Also

- [Inference Server](inference-server.md) — `/transcribe`
- [WhisperX Compat](whisper-x-compat.md) — PyTorch/TorchAudio/cuDNN compatibility helpers
- [Pipeline Tasks](../web/backend/pipeline-tasks.md) — Transcribes extracted reference-video audio for lip-sync jobs
