FROM node:22-bookworm-slim AS frontend

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build


FROM node:22-bookworm-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    ENABLE_PARTNER_MCP=true \
    ENABLE_MONGODB_MCP=true \
    MONGODB_MCP_READ_ONLY=true

RUN python3 -m venv /opt/venv
RUN npm install -g mongodb-mcp-server

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip \
    && pip install --prefer-binary -r /app/backend/requirements.txt

COPY backend /app/backend
COPY pharma-briefing-agent /app/pharma-briefing-agent
COPY --from=frontend /app/frontend/dist /app/frontend/dist

WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
