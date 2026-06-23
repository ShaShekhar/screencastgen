# WhisperX Compat

> Compatibility helpers for WhisperX under newer PyTorch/TorchAudio and mixed CUDA runtime environments.

**Source:** [`screencastgen/whisperx_compat.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/whisperx_compat.py)

---

## Responsibilities

| Helper | Purpose |
|--------|---------|
| `resolve_whisperx_device(device)` | Falls back to CPU for WhisperX when CUDA is selected but `libcudnn_ops_infer.so.8` is unavailable |
| `patch_torchaudio_audiometadata()` | Restores the legacy `torchaudio.AudioMetaData` name expected by some pyannote/WhisperX imports |
| `allow_unsafe_torch_load()` | Temporarily forces `torch.load(weights_only=False)` while trusted WhisperX checkpoints load |
| `load_whisperx_model()` | Loads WhisperX ASR with compatibility patches |
| `load_whisperx_align_model()` | Loads WhisperX alignment model with compatibility patches |

---

## Why It Exists

- PyTorch 2.6 changed the default `torch.load` behavior to `weights_only=True`, which breaks some trusted WhisperX/pyannote checkpoints.
- Newer TorchAudio releases removed or moved a top-level metadata type that older pyannote annotations expect.
- Some GPU VM images have CUDA available but lack the cuDNN 8 runtime required by WhisperX dependencies.

The helpers scope monkey patches tightly around model loading and avoid crashing the whole GPU server when only WhisperX needs to fall back to CPU.

---

## See Also

- [WhisperX Provider](../providers/whisper-x-provider.md) — Forced alignment provider
- [Transcription](transcription.md) — ASR-only helper
- [Inference Server](inference-server.md) — Uses both transcription and alignment
