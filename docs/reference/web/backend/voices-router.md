# Voices Router

> Bundled voice library endpoints.

**Source:** [`web/backend/routers/voices.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/routers/voices.py)

---

## Endpoints

### `GET /api/voices`
List all bundled voices from the manifest.

**Response:** `List[BundledVoice]` — Each voice has id, name, language, description, ref_text, available flag.

### `GET /api/voices/{voice_id}/audio`
Serve the audio sample file for a bundled voice.

**Response:** Audio file stream.

### `GET /api/languages`
List supported languages.

**Response:** `List[{code, name}]`

### `POST /api/voices/preview`
Generate a TTS preview with a given voice.

**Request:**
| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Preview text (optional, uses default) |
| `language` | `str` | Language code |
| `voice_id` | `str` | Bundled voice ID (optional) |
| `ref_audio_file_id` | `str` | Custom ref audio (optional) |
| `ref_text` | `str` | Reference transcript (optional) |
| `uploaded_file_id` | `str` | Optional document upload; server extracts a representative text snippet when `text` is omitted |

**Response:** Audio file bytes.

When neither `text` nor a document snippet is available, the router falls back to a generic preview sentence. With a reference audio selected, it calls the GPU server `/synthesize` endpoint as multipart form data so per-request voice cloning can use `ref_audio` and `ref_text`.

---

## Dependencies

```
Voices Router
├── Voices Service    (load_voices, get_voice)
├── Storage Service   (uploaded reference/document paths)
├── Extractor         (document snippet extraction)
└──▶ consumed by Voices API (frontend)
     └──▶ used by VoiceSettings
```

---

## See Also

- [Voices Service](voices-service.md) — Voice manifest loader
- [VoiceSettings](../frontend/voice-settings.md) — Frontend voice picker
- [Voices API](../frontend/voices-api.md) — Frontend API client
