# Web Logging

> Logging configuration for backend and worker components.

**Source:** [`web/backend/logging_config.py`](https://github.com/ShaShekhar/screencastgen/blob/main/web/backend/logging_config.py)

---

## Function

### `setup_logging(component: str)`
Configures Python logging for the specified component (`"backend"` or `"worker"`).

Sets up:
- Log level
- Format string
- Handler configuration

Called during [FastAPI App](fast-api-app.md) startup and [Celery App](celery-app.md) worker init.

---

## Dependencies

```
Web Logging
├── logging (stdlib)
└──▶ consumed by FastAPI App
     └──▶ consumed by Celery App
```

---

## See Also

- [FastAPI App](fast-api-app.md) — Backend logging setup
- [Celery App](celery-app.md) — Worker logging setup
