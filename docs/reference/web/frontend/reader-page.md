# Reader Page

> Full-screen browser reader for completed highlight/lip-sync jobs with synchronized playback, word highlighting, and optional presenter video.

**Source:** [`web/frontend/src/pages/Reader.tsx`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/pages/Reader.tsx)
**Route:** `/jobs/:id/read`

---

## Features

- **Manifest-driven rendering** — Loads a `ReaderManifest` and renders page-grouped chunks with per-word timings
- **Word-level sync** — Highlights the active word based on audio playback time
- **Clickable seeking** — Clicking a word seeks the audio to that word and starts playback if needed
- **Comfort-band auto-scroll** — Keeps the active word within roughly the 25% to 65% vertical band before scrolling again
- **Page image preview** — Shows the active PDF page image in a sticky side panel when page assets exist
- **Presenter PiP** — Lip-sync reader jobs use `presenter.mp4` as the playback clock in a draggable, edge-resizable picture-in-picture frame
- **Offline reader download** — The primary lip-sync job artifact is a standalone ZIP containing the local viewer and all required assets
- **On-demand EPUB export** — Completed lip-sync reader jobs can trigger and download a text-and-narration EPUB; presenter video is omitted and reading-system support varies
- **Playback dock** — Bottom control bar with play/pause, scrubber, duration, playback speed, and auto-scroll toggle
- **Deferred control hiding** — Playback controls stay visible before first play, then auto-hide after inactivity near the bottom edge
- **Graceful fallback** — Shows a reader-unavailable message and a back link when the manifest is missing

---

## State

| State | Type | Description |
|-------|------|-------------|
| `manifest` | `ReaderManifest \| null` | Reader metadata and timed chunks |
| `error` | `string \| null` | Reader load failure message |
| `loading` | `boolean` | Initial manifest fetch state |
| `activeIdx` | `number` | Active flattened word index |
| `playing` | `boolean` | Current audio playback state |
| `rate` | `number` | Playback speed |
| `currentTime` | `number` | Current audio time in seconds |
| `autoScroll` | `boolean` | Whether reader follows the active word |
| `controlsVisible` | `boolean` | Visibility of the bottom playback dock |
| `hasStartedPlaying` | `boolean` | Tracks whether autoplay-style control hiding should activate |
| `theme` | `"night" \| "pdf"` | Persisted reader color theme |
| `pipWidth` | `number` | Persisted presenter PiP width |
| `pipPos` | `{x, y}` | Persisted presenter PiP position |
| `epubStatus` | `EpubExportStatus` | On-demand EPUB export state |
| `epubError` | `string \| null` | EPUB export failure detail |

---

## API Calls

- `getReaderManifest(id)` from [Reader API](reader-api.md) — initial manifest fetch
- `getReaderAudioUrl(id)` from [Reader API](reader-api.md) — `<audio>` source URL
- `getReaderPresenterUrl(id)` from [Reader API](reader-api.md) — `<video>` presenter source URL
- `getReaderPageUrl(id, filename)` from [Reader API](reader-api.md) — sticky page-preview image URL
- `getDownloadUrl(id)` from [Jobs API](jobs-api.md) — standalone offline-reader ZIP
- `requestEpubExport(id)`, `getEpubExportStatus(id)`, `getEpubExportDownloadUrl(id)` from [Jobs API](jobs-api.md) — text-and-narration EPUB export

---

## Interaction Model

1. Fetch the manifest for the job-specific reader route
2. Flatten chunk words into a searchable timeline for binary-search lookup
3. Update `activeIdx` from audio `timeupdate` events
4. Smooth-scroll only when the active word leaves the comfort band
5. For lip-sync jobs, use the presenter video as the media element; for highlight jobs, use audio
6. Let users drag the presenter and resize it from the right/bottom edges or bottom-right corner
7. Cancel automatic scrolling when the user manually scrolls or swipes
8. Hide the playback dock only after playback has started and the pointer is idle away from the bottom edge

---

## See Also

- [JobDetail Page](job-detail-page.md) — Entry point into the browser reader
- [Reader API](reader-api.md) — Reader client helpers
- [Jobs API](jobs-api.md) — Download URL helper
