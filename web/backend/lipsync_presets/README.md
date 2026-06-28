# Bundled Lip-Sync Presets

This directory holds presenter video/audio presets for the "Lip-Sync Video Reader" pipeline.

## Adding a preset

1. Drop a clean presenter video into this folder, ideally 5-15 seconds with one visible speaking face and clean speaker audio.
2. Optionally drop a matching clean WAV reference audio clip into this folder, ideally 10-20 seconds, mono, 16/24 kHz. Use this only when you want to override the audio embedded in the presenter video.
3. Add an entry to `manifest.json` with:
   - `id` - stable slug used in API requests
   - `name` - display name shown in the UI
   - `language` - BCP-47 tag, e.g. `en-US`
   - `description` - short blurb shown under the name
   - `video_file` - presenter video filename relative to this directory
   - `audio_file` - optional reference audio filename relative to this directory
   - `ref_text` - exact transcript of the reference audio; if omitted, the worker will transcribe the extracted audio

## Same face and voice

For the usual case where the presenter video already contains the voice you want to clone, leave `audio_file` empty or omit it:

```json
{
  "presets": [
    {
      "id": "default-presenter",
      "name": "Default Presenter",
      "language": "en-US",
      "description": "Default bundled presenter.",
      "video_file": "default-presenter.mp4",
      "audio_file": "",
      "ref_text": "Exact transcript of the speech in the presenter video."
    }
  ]
}
```

## Notes

- When a bundled preset is selected, uploaded lip-sync reference files are ignored by design.
- `audio_file` can be left empty when the presenter video has clean speaker audio; the worker will extract a voice reference from the video.
- The manifest is read on every request, so adding/editing presets does not require a server restart.
