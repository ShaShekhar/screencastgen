# LipsyncSettings

> Reference video, optional audio override, and presenter configuration.

**Source:** [`web/frontend/src/components/LipsyncSettings.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/components/LipsyncSettings.tsx)

---

## Props

```typescript
{
  config: LipsyncConfig
  onChange: (config: LipsyncConfig) => void
}
```

---

## Fields

| Control | Type | Description |
|---------|------|-------------|
| Reference video | [FileUploader](file-uploader.md) | Face and voice video (~10s clip); embedded audio is used as the default voice reference |
| Reference audio override | [FileUploader](file-uploader.md) | Optional audio clip when the reference video's audio should not be used |
| Face position | select | `bottom-right`, `top-right`, `bottom-left`, `top-left`, `left`, `right`, `center` |
| LatentSync preset | select | `small` (256px fast) or `quality` (512px, default) |
| Presenter scale | slider | 0.12 – 0.4 |

---

## State

| State | Type | Description |
|-------|------|-------------|
| `audioName` | `string \| null` | Uploaded override audio filename |
| `videoName` | `string \| null` | Uploaded reference video filename |

---

## Used By

- [NewJob Page](new-job-page.md) — When pipeline is `lipsync`

---

## See Also

- [VoiceSettings](voice-settings.md) — Alternative for highlight pipeline
- [Lipsync Pipeline](../../pipelines/lipsync-pipeline.md) — What these settings configure
- [LatentSync Provider](../../providers/latent-sync-provider.md) — Provider presets
