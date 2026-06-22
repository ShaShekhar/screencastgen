# Bundled Reference Voices

This directory holds reference audio clips that the web UI offers as preset voices for the "Highlight Text Audio" pipeline.

## Adding a voice

1. Drop a clean WAV clip (~10–20 seconds, mono, 16/24 kHz) into this folder.
2. Add an entry to `manifest.json` with:
   - `id` — stable slug (used in API requests)
   - `name` — display name shown in the UI
   - `language` — BCP-47 tag, e.g. `en-US`
   - `description` — short blurb shown under the name
   - `file` — filename relative to this directory
   - `ref_text` — exact transcript of the WAV clip (used by Qwen3-TTS for voice cloning)

## Notes

- Clips should contain a single speaker with no background music.
- Users can still upload their own one-off reference clip from the New Job page; bundled voices are just convenient presets.
- The manifest is read on every request, so adding/editing voices does not require a server restart.
