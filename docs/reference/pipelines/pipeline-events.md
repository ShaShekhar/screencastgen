# Pipeline Events

> Structured progress reporting for pipelines.

**Source:** [`screencastgen/pipelines/events.py`](https://github.com/ShaShekhar/screencastgen/blob/main/screencastgen/pipelines/events.py)

---

## Overview

`PipelineReporter` bridges human-readable console output and machine-parseable structured events. Pipelines call reporter methods at each phase; consumers (CLI stdout, [web progress bridge](../web/backend/progress-reporter.md)) receive the output.

---

## Dataclass

### `PipelineEvent`

| Field | Type | Description |
|-------|------|-------------|
| `status` | `str` | Current status (e.g., `"running"`, `"completed"`) |
| `phase` | `str` | Current phase name |
| `current` | `int` | Progress numerator |
| `total` | `int` | Progress denominator |
| `message` | `str` | Human-readable description |
| `data` | `dict \| None` | Optional structured payload for richer UI updates, such as lip-sync page timing |

---

## Class: `PipelineReporter`

### Constructor
```python
PipelineReporter(stream=sys.stdout, on_event=None, should_cancel=None)
```

`on_event` is a callback `(PipelineEvent) -> None` for structured event consumers. `should_cancel` is an optional callback used by long-running hosts such as the web worker.

### Methods

| Method | Description |
|--------|-------------|
| `cancelled()` | Returns whether the host requested early cancellation |
| `line(message)` | Write a human-readable line to the stream |
| `emit(phase, current, total, message, status="running", data=None)` | Publish a structured event and update internal state |
| `phase_start(phase, message)` | Announce a phase transition |

---

## Event Flow

```
Pipeline Runner
    │
    ├── reporter.phase_start("extraction", "Extracting text...")
    ├── reporter.emit("synthesis", 1, 10, "Chunk 1/10")
    ├── reporter.emit("synthesis", 2, 10, "Chunk 2/10")
    │   ...
    └── reporter.emit("complete", 10, 10, "Done", status="completed")
         │
         ▼
    ┌────────────────┐     ┌──────────────────────┐
    │  CLI stdout    │     │ Progress Reporter   │
    │  (human text)  │     │  (DB + Redis pubsub)  │
    └────────────────┘     └──────────────────────┘
```

---

## Dependencies

```
Pipeline Events
└──▶ consumed by Audio Pipeline
     ├──▶ Highlight Pipeline
     ├──▶ Lipsync Pipeline
     ├──▶ Pipeline Common
     └──▶ Progress Reporter (web app)
```

---

## See Also

- [Pipeline Overview](../../concepts/pipelines.md) — How events fit into pipeline design
- [Progress Reporter](../web/backend/progress-reporter.md) — Web app consumer of events
- [Events Router](../web/backend/events-router.md) — SSE delivery to browser
