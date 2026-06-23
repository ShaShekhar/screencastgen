# TTS Registry

> Central registry for TTS backend lookup, creation, and CLI/server arg registration.

**Source:** [`screencastgen/providers/tts/__init__.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/tts/__init__.py)

---

## Overview

Maintains a mapping of `name -> BackendSpec` for all TTS backends. Creation is lazy, so backend modules are imported only when needed.

Context names in this registry are the actual parser contexts used in code:
- `cli`
- `server`
- `download` for model-download-only arguments

---

## Functions

### Lookup

| Function | Description |
|----------|-------------|
| `get_backend_names(context) -> List[str]` | List backend names available in a context |
| `get_default_backend_name(context, preferred="qwen") -> str` | Get the default backend for a context |
| `get_backend_spec(name) -> BackendSpec` | Get the spec for a named backend |
| `iter_backend_specs(context) -> List[BackendSpec]` | Iterate specs for a context |

### Creation

| Function | Description |
|----------|-------------|
| `create_backend(name, **kwargs)` | Lazy-import and instantiate a backend |
| `create_backend_from_args(args, invocation)` | Validate args and create a backend from parsed inputs |

### Parser Integration

| Function | Description |
|----------|-------------|
| `register_backend_args(parser, context)` | Add backend-specific args to a parser |
| `register_backend_download_args(parser)` | Add model-download arguments |
| `get_downloadable_backend_names()` | List backends with downloadable models |

---

## Registered Backends

| Name | Spec Module | Class | Contexts |
|------|-------------|-------|----------|
| `qwen` | [Qwen Backend](qwen-backend.md) | `QwenTTS` | `cli`, `server` |
| `remote` | [Remote TTS](remote-tts.md) | `RemoteTTS` | `cli` |

---

## Dependencies

```
TTS Registry
├── TTS Base           (BackendSpec, BackendArg)
├── Qwen Backend       (lazy import)
├── Remote TTS         (lazy import)
└──▶ consumed by Pipeline Common
     ├──▶ CLI
     ├──▶ Models
     └──▶ Inference Server
```

---

## See Also

- [TTS Base](tts-base.md) — `BackendSpec` and `BackendArg` definitions
- [Provider Overview](../../concepts/providers.md) — Registry pattern explanation
- [Types](../core/types.md) — `TTSBackend` protocol
