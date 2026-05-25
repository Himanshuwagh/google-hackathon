# PharmaOps Frontend

React + Vite dashboard for the PharmaOps ADK agent.

For Cloud Run, the root `Dockerfile` builds this frontend and copies `dist/`
into the FastAPI container so the hosted project URL serves both UI and API.

Local development:

```bash
npm install
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```
