# PharmaOps MongoDB-Only Implementation Plan

This repo now targets the Google Cloud Rapid Agent Hackathon MongoDB partner
track with MongoDB Atlas as the private retrieval and storage layer.

## Runtime Shape

```text
React dashboard
  -> FastAPI on Cloud Run
    -> Google ADK SequentialAgent
      -> Gemini planner / retriever / writer / quality gate / compliance / action agents
      -> MongoDB MCP server for read-only partner reads
      -> MongoDB Atlas for operational data, CRM memory, document search,
         competitive intel, vector embeddings, run traces, and briefings
      -> PubMed and ClinicalTrials.gov for public evidence
```

## Private Retrieval

MongoDB Atlas collections:

- `company_docs`: clinical documents, datasheets, source links, embeddings.
- `crm_memory`: HCP visit history, relationship notes, objections.
- `competitive_intel`: competitor context, weakness tags, embeddings.

Runtime tool names remain stable:

- `search_company_docs(query_text, drug_id)`
- `search_crm_memory(hcp_id)`
- `search_competitive_intel(query_text, therapeutic_area)`

The tools use Atlas Vector Search and Atlas Search when available, then merge
ranked results with reciprocal-rank fusion. Local/dev fallback uses MongoDB
filters and deterministic text scoring so smoke tests can run without Atlas
Search indexes.

## Data Setup

```bash
cd pharma-briefing-agent
python db/seed_data.py
python db/seed_mongodb_retrieval.py
```

The retrieval seed script loads `mongo_company_docs.json`,
`mongo_crm_memory.json`, and `mongo_competitive_intel.json`, creates normal
MongoDB indexes, and best-effort creates Atlas Search/vector indexes.

## Verification

```bash
cd pharma-briefing-agent
../.venv/bin/python test_mongodb_mcp_runtime.py
../.venv/bin/python test_evidence_grounding.py
../.venv/bin/python test_mongo_retrieval_tools.py
```

```bash
cd frontend
npm run build
```
