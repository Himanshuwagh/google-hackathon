# PharmaOps Agent

PharmaOps is a Google ADK + Gemini agent workflow for pharma sales reps. When a
rep adds a doctor meeting, the agent plans the prep, retrieves evidence,
checks promotional compliance, writes a briefing, and exposes the result in a
web dashboard.

## Hackathon Alignment

- **Google Cloud Rapid Agent Hackathon track:** MongoDB partner track.
- **Agent platform:** Google ADK code-first agent runtime, deployed on Google
  Cloud Run. This aligns with Vertex AI Agent Builder's ADK path while keeping
  the existing FastAPI dashboard.
- **Partner MCP:** The ADK agents load the official MongoDB MCP server through
  `McpToolset` with the `mongodb` tool prefix. It runs read-only by default for
  schema/data inspection while deterministic app tools perform controlled
  writes.
- **Gemini:** Each agent step is a Gemini-backed `LlmAgent`.
- **Web platform:** React frontend and FastAPI backend are packaged into one
  Cloud Run service.

The runtime status endpoint is:

```text
/agent-runtime
```

Use it in the demo to show ADK, Gemini, Cloud Run, and partner MCP status.

## Architecture

```text
React dashboard
  -> FastAPI on Cloud Run
    -> Google ADK SequentialAgent
      -> Gemini planner / retriever / writer / compliance / action agents
      -> MongoDB MCP server for partner data inspection
      -> MongoDB Atlas for meetings, compliance rules, briefings, run logs
      -> Elasticsearch for company docs, CRM memory, competitive intel
      -> PubMed and ClinicalTrials.gov for public evidence lookup
```

## Required Environment

Store these as Cloud Run environment variables or Secret Manager secrets:

```text
MONGO_URI
MONGO_DB_NAME
GOOGLE_API_KEY
ELASTIC_URL
ELASTIC_API_KEY
GOOGLE_LOCATION=us-central1
ENABLE_PARTNER_MCP=true
ENABLE_MONGODB_MCP=true
MONGODB_MCP_READ_ONLY=true
```

Optional Elastic MCP endpoint:

```text
ENABLE_ELASTIC_MCP=true
ELASTIC_MCP_URL=https://<elastic-mcp-host>/mcp
ELASTIC_MCP_AUTH_HEADER="ApiKey <key>"
```

## Deploy To Cloud Run

Install and authenticate the Google Cloud CLI, then set your project:

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud auth login
gcloud auth application-default login
```

Enable required services:

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com
```

Create the Artifact Registry repository once:

```bash
gcloud artifacts repositories create pharmaops \
  --repository-format=docker \
  --location=us-central1 \
  --description="PharmaOps Cloud Run images"
```

Create secrets. Run each command with your real value in the shell variable:

```bash
printf "%s" "$MONGO_URI" | gcloud secrets create MONGO_URI --data-file=-
printf "%s" "$MONGO_DB_NAME" | gcloud secrets create MONGO_DB_NAME --data-file=-
printf "%s" "$GOOGLE_API_KEY" | gcloud secrets create GOOGLE_API_KEY --data-file=-
printf "%s" "$ELASTIC_URL" | gcloud secrets create ELASTIC_URL --data-file=-
printf "%s" "$ELASTIC_API_KEY" | gcloud secrets create ELASTIC_API_KEY --data-file=-
```

Allow the Cloud Run service account to read secrets:

```bash
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for SECRET in MONGO_URI MONGO_DB_NAME GOOGLE_API_KEY ELASTIC_URL ELASTIC_API_KEY; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
done
```

Build and deploy:

```bash
gcloud builds submit \
  --config cloudbuild.yaml \
  --substitutions _REGION=us-central1,_SERVICE=pharmaops-agent
```

After deploy, verify:

```bash
SERVICE_URL=$(gcloud run services describe pharmaops-agent \
  --region=us-central1 \
  --format="value(status.url)")

curl "$SERVICE_URL/health"
curl "$SERVICE_URL/agent-runtime"
```

Open `$SERVICE_URL` in the browser for the dashboard.

## Local Development

Backend:

```bash
cd backend
../.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm install
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Agent package:

```bash
cd pharma-briefing-agent
pip install -r requirements.txt
python db/seed_data.py
python db/seed_elastic.py
```
