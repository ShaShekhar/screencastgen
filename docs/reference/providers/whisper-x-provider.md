# WhisperX Provider

> Word-level audio-text alignment using WhisperX.

**Source:** [`screencastgen/providers/align/whisperx_provider.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/align/whisperx_provider.py)

---

## Function

### `align_with_whisperx(audio_path, text, language="en-US", device="auto") -> List[WordTiming]`

Uses WhisperX 3.1 to:
1. Load the `"base"` whisper model
2. Transcribe the audio (to get initial segments)
3. Load a language-specific alignment model
4. Perform word-level alignment

**Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `audio_path` | `str` | — | Audio file to align |
| `text` | `str` | — | Known transcript |
| `language` | `str` | `"en-US"` | Language code |
| `device` | `str` | `"auto"` | Compute device |

**Returns:** `List[`[WordTiming](../core/types.md)`]` with `word`, `start`, `end` per word.

---

## How It Works

```
Audio file + Text
    │
    ▼  whisperx.load_model("base")
Whisper model
    │
    ▼  model.transcribe(audio)
Transcription segments
    │
    ▼  whisperx.load_align_model(language)
Alignment model
    │
    ▼  whisperx.align(segments, model)
Word-level alignments
    │
    ▼  convert to List[WordTiming]
```

---

## Dependencies

```
WhisperX Provider
├── whisperx >= 3.1    (deferred import)
├── torch              (deferred import)
├── `whisperx_compat.py`
└──▶ registered in Alignment Registry
     └──▶ called by Aligner
```

---

## Runtime Notes

- WhisperX model loading is wrapped by `screencastgen/whisperx_compat.py` to force `torch.load(..., weights_only=False)` for trusted WhisperX and pyannote checkpoints on PyTorch 2.6+.
- When the selected device is `cuda`, the compatibility layer also checks for `libcudnn_ops_infer.so.8`.
- If that cuDNN 8 runtime is missing, the provider logs a warning and falls back to CPU for WhisperX instead of aborting the server process.
- This fallback is scoped to WhisperX. Other GPU-backed components can still use CUDA if their own runtime requirements are satisfied.

### GPU VM Troubleshooting

If alignment crashes with an error like:

```text
Could not load library libcudnn_ops_infer.so.8
```

the VM usually has a CUDA-visible PyTorch install but no cuDNN 8 runtime on the dynamic loader path. Check:

```bash
ldconfig -p | grep cudnn
find "$VIRTUAL_ENV" -name 'libcudnn_ops_infer.so*' 2>/dev/null
python -c "import torch; print(torch.__version__, torch.version.cuda)"
```

If the library exists inside the active venv, export its containing directory before starting the inference server:

```bash
export CUDNN_LIB_DIR="$VIRTUAL_ENV/lib/python3.10/site-packages/nvidia/cudnn/lib"
export LD_LIBRARY_PATH="$CUDNN_LIB_DIR:$LD_LIBRARY_PATH"
python -c "import ctypes; ctypes.CDLL('libcudnn_ops_infer.so.8'); print('ok')"
```

If it is absent, install a cuDNN 8 runtime in that environment, for example:

```bash
uv pip install "nvidia-cudnn-cu12<9"
```

---

## See Also

- [Alignment Registry](alignment-registry.md) — Provider registration
- [Aligner](../core/aligner.md) — Facade API
- [Types](../core/types.md) — `WordTiming` dataclass
- [Remote GPU Client](../core/remote-gpu-client.md) — Remote alignment alternative
