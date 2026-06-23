# TTS Base

> Base classes and utilities for TTS backends.

**Source:** [`screencastgen/providers/tts/base.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/tts/base.py)

---

## Functions

### `resolve_device(device="auto") -> str`
Resolves `"auto"` to `"cuda"` (if available) or `"cpu"`. Used by all GPU-capable backends.

---

## Dataclasses

### `BackendArg`
Defines a CLI argument for a TTS backend.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Argument name (e.g., `"--model"`) |
| `type` | type | Argument type |
| `default` | any | Default value |
| `help` | `str` | Help text |
| `choices` | list | Valid values |

### `BackendSpec`
Metadata for a TTS backend.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Backend identifier (e.g., `"qwen"`) |
| `module_path` | `str` | Module to import |
| `class_name` | `str` | Class to instantiate |
| `contexts` | `List[str]` | Where it can run (`"local"`, `"server"`) |
| `capabilities` | `List[str]` | Features (`"voice_clone"`, `"requires_ref_audio"`) |
| `extra_args` | `List[BackendArg]` | Additional CLI arguments |
| `download_args` | `List[BackendArg]` | Model download arguments |
| `build_kwargs` | `callable` | Extracts constructor kwargs from args |
| `validate` | `callable` | Validates args before creation |
| `download_models` | `callable` | Downloads model files |

---

## Usage Pattern

```python
spec = get_backend_spec("qwen")
kwargs = spec.build_kwargs(args)          # Extract from argparse
spec.validate(args)                       # Check requirements
backend = create_backend("qwen", **kwargs) # Lazy import + instantiate
```

---

## Dependencies

```
TTS Base
├── torch (deferred, for resolve_device)
└──▶ consumed by TTS Registry
     ├──▶ Qwen Backend (spec definition)
     ├──▶ Remote TTS (spec definition)
     └──▶ Lipsync Facade (resolve_device)
```

---

## See Also

- [TTS Registry](tts-registry.md) — Uses specs for backend management
- [Types](../core/types.md) — `TTSBackend` protocol that backends implement
- [Provider Overview](../../concepts/providers.md) — Registry pattern explanation
