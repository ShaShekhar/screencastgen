# VoiceSettings

> Bundled/custom voice picker with preview.

**Source:** [`web/frontend/src/components/VoiceSettings.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/components/VoiceSettings.tsx)

---

## Props

```typescript
{
  config: HighlightConfig | AudioConfig
  onChange: (config: Partial<HighlightConfig>) => void
  uploadedFileId?: string | null
}
```

---

## Features

### Voice Source Toggle
- **Bundled** — Select from pre-installed voices
- **Custom** — Upload reference audio clip

### Bundled Voice Picker
- Fetches voice list from [listVoices()](voices-api.md)
- Displays available voices with language tags
- Audio preview playback
- Auto-selects first available voice

### Custom Voice Upload
- [FileUploader](file-uploader.md) for reference audio
- Uploaded reference audio is transcribed internally when the pipeline job runs

### Additional Controls
- **Language selector** — from [listLanguages()](voices-api.md)
- **Voice preview** — Generate TTS sample via [previewVoice()](voices-api.md)
- **Document-aware preview** — Passes `uploadedFileId` so the preview endpoint can use a snippet from the user's document when supported

---

## State

| State | Type | Description |
|-------|------|-------------|
| `voices` | `BundledVoice[]` | Available voices |
| `languages` | `LanguageOption[]` | Available languages |
| `loadError` | `string \| null` | Voice/language loading error |
| `voiceSource` | `"bundled" \| "upload"` | Selected source |
| `uploadedRefName` | `string \| null` | Uploaded custom voice filename |
| `previewLoading` | `boolean` | Preview generation in progress |
| `previewError` | `string \| null` | Preview error |
| `previewUrl` | `string \| null` | Blob URL for preview audio |

---

## Used By

- [NewJob Page](new-job-page.md) — When pipeline is `highlight`

---

## See Also

- [Voices API](voices-api.md) — API client
- [Voices Router](../backend/voices-router.md) — Backend endpoints
- [Voices Service](../backend/voices-service.md) — Voice manifest
- [LipsyncSettings](lipsync-settings.md) — Alternative for lipsync pipeline
