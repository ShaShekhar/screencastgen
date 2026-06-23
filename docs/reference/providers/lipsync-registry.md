# Lipsync Registry

> Registry for lip-sync video generation providers.

**Source:** [`screencastgen/providers/lipsync/__init__.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/lipsync/__init__.py), [`screencastgen/providers/lipsync/base.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/providers/lipsync/base.py)

---

## Overview

Manages lip-sync providers that take audio + reference video and produce a lip-synced face video.

---

## Functions

| Function | Description |
|----------|-------------|
| `get_lipsync_provider_names() -> List[str]` | Returns `["auto", "latentsync"]` |
| `get_default_lipsync_provider() -> str` | Returns `"auto"` |
| `get_auto_lipsync_provider() -> str` | Returns the first registered concrete provider (`"latentsync"`) |
| `get_lipsync_provider_spec(name) -> LipsyncProviderSpec` | Get provider spec |
| `run_lipsync_provider(provider, video_path, audio_path, output_path, device, **kwargs)` | Dispatch to named provider |

The `"auto"` value resolves to the first registered concrete provider. It currently selects LatentSync and reports a configuration error if that runtime is unavailable; it does not fall back to an unregistered implementation.

---

## Dataclass: `LipsyncProviderSpec`
Defined in `base.py`. Metadata for a lip-sync provider.

---

## Registered Providers

| Name | Module | Description |
|------|--------|-------------|
| `auto` | — | Select the first registered provider (currently LatentSync) |
| `latentsync` | [LatentSync Provider](latent-sync-provider.md) | High-quality lip-sync |

**Default:** `auto`

---

## Dependencies

```
Lipsync Registry
├── LatentSync Provider  (lazy import)
├── LipsyncProviderSpec      (base.py)
└──▶ consumed by Lipsync Facade
     └──▶ consumed by Lipsync Pipeline
```

---

## See Also

- [Lipsync Facade](../core/lipsync-facade.md) — Facade that wraps this registry
- [LatentSync Provider](latent-sync-provider.md) — Primary lip-sync implementation
- [Provider Overview](../../concepts/providers.md) — Registry pattern
