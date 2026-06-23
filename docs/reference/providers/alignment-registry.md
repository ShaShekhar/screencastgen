# Alignment Registry

> Registry for word-level alignment providers.

**Source:** [`screencastgen/providers/align/__init__.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/align/__init__.py), [`screencastgen/providers/align/base.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/align/base.py)

---

## Overview

Manages alignment providers that take audio + text and produce word-level timing data ([WordTiming](../core/types.md)). Currently only WhisperX is registered.

---

## Functions

| Function | Description |
|----------|-------------|
| `get_alignment_provider_names() -> List[str]` | List registered providers |
| `get_default_alignment_provider() -> str` | Returns `"whisperx"` |
| `get_alignment_provider_spec(name) -> AlignmentProviderSpec` | Get provider spec |
| `align_with_provider(provider, audio_path, text, language, device) -> List[WordTiming]` | Dispatch alignment to named provider |

---

## Dataclass: `AlignmentProviderSpec`
Defined in `base.py`. Metadata for an alignment provider.

---

## Registered Providers

| Name | Module | Description |
|------|--------|-------------|
| `whisperx` | [WhisperX Provider](whisper-x-provider.md) | WhisperX word-level alignment |

**Default:** `whisperx`

---

## Dependencies

```
Alignment Registry
├── WhisperX Provider  (lazy import)
├── AlignmentProviderSpec  (base.py)
└──▶ consumed by Aligner
     └──▶ consumed by Pipeline Common
```

---

## See Also

- [Aligner](../core/aligner.md) — Facade that wraps this registry
- [WhisperX Provider](whisper-x-provider.md) — The default alignment implementation
- [Provider Overview](../../concepts/providers.md) — Registry pattern
