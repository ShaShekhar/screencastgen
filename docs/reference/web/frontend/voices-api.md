# Voices API

> Voice library listing, preview, and language queries.

**Source:** [`web/frontend/src/api/voices.ts`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/api/voices.ts)

---

## Functions

| Function | HTTP | Endpoint | Description |
|----------|------|----------|-------------|
| `listVoices()` | GET | `/api/voices` | List bundled voices |
| `voiceAudioUrl(voiceId)` | — | `/api/voices/{id}/audio` | Returns URL string |
| `listLanguages()` | GET | `/api/languages` | List supported languages |
| `previewVoice(params)` | POST | `/api/voices/preview` | Generate TTS preview, returns blob URL |

### `previewVoice` Parameters

```typescript
{
  text?: string
  language: string
  voice_id?: string
  ref_audio_file_id?: string
  ref_text?: string
  uploaded_file_id?: string
}
```

Returns a blob URL for `<audio>` playback. The caller is responsible for revoking the URL when replacing/unmounting the preview.

---

## Consumers

- [VoiceSettings](voice-settings.md) — Voice picker and preview

---

## Backend

Calls [Voices Router](../backend/voices-router.md) endpoints.

---

## See Also

- [API Client](api-client.md) — Base Axios instance
- [VoiceSettings](voice-settings.md) — Component that uses this
- [Voices Router](../backend/voices-router.md) — Backend endpoints
