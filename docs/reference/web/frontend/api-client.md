# API Client

> Axios base instance for all API calls.

**Source:** [`web/frontend/src/api/client.ts`](https://github.com/ShaShekhar/screencastgen/blob/main/web/frontend/src/api/client.ts)

---

## Configuration

```typescript
const client = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" }
})
```

The `/api` prefix is proxied by Vite to the backend (port 8000) during development.

---

## Consumers

- [Jobs API](jobs-api.md) — Job CRUD operations
- [Uploads API](uploads-api.md) — File uploads
- [Voices API](voices-api.md) — Voice library

---

## See Also

- [FastAPI App](../backend/fast-api-app.md) — Backend API server
- [Frontend Overview](frontend-overview.md) — Frontend architecture
