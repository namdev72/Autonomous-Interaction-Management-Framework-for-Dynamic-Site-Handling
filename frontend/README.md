# Frontend

React + TypeScript + Vite UI for the agent: submit a task, watch the agent's steps live over a WebSocket, answer its questions, and view results and comparison tables.

```powershell
npm install
npm run dev      # http://localhost:5173
npm run build    # type-check and production build into dist/
```

The UI talks to the backend at `http://localhost:8000` by default. To use another backend, create `frontend/.env` with `VITE_API_URL=http://<host>:8000`.

See the [project README](../README.md) for the backend and overall setup.
