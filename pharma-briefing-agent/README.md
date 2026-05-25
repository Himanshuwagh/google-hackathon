# PharmaOps Sales Agent

> Autonomous AI briefing workflow for pharmaceutical sales reps in India.  
> Built for the **Google Cloud Rapid Agent Hackathon** MongoDB partner track.

## What It Does

When a new doctor meeting is added to MongoDB, the agent **automatically**:

1. **Detects** the new meeting via MongoDB Change Stream
2. **Plans** an execution strategy using Gemini
3. **Retrieves** internal docs from Elastic + live evidence from PubMed/ClinicalTrials.gov
4. **Writes** personalised talking points
5. **Validates** against India's UCPMP 2024 pharmaceutical marketing law
6. **Saves** the briefing to MongoDB and exposes the result in the PharmaOps dashboard
7. **Rep wakes up** to find everything done — no prompts, no clicks

**This is NOT a chatbot.** The agent runs end-to-end in the background.

## Hackathon Runtime Notes

- The agent is built with Google ADK `SequentialAgent` + Gemini `LlmAgent`
  stages.
- The ADK runtime loads the official MongoDB MCP server through
  `tools/mcp_servers.py` using `McpToolset`.
- MongoDB MCP is read-only by default so the agent can inspect partner data
  safely. Controlled writes still go through deterministic application tools.
- The web app is deployed as a single Google Cloud Run service from the root
  `Dockerfile`.

## Tech Stack

| Component | Tool |
|---|---|
| AI Runtime | Google ADK + Gemini on Google Cloud Run |
| Partner MCP | MongoDB MCP Server via ADK `McpToolset` |
| Database | MongoDB Atlas |
| Doc Search | Elasticsearch |
| Evidence | PubMed API, ClinicalTrials.gov API, OpenFDA API |
| Frontend | React on Google Cloud Run |

## Setup

```bash
# 1. Clone and install
cd pharma-briefing-agent
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 3. Seed demo data into MongoDB
python db/seed_data.py

# 4. Seed Elastic index
python db/seed_elastic.py

# 5. Start the agent
python trigger.py
```

## Project Structure

```
pharma-briefing-agent/
├── agent/                  # ADK agent definitions
│   ├── main_agent.py       # SequentialAgent orchestrator
│   ├── planner_agent.py    # Reads meeting, builds plan
│   ├── retriever_agent.py  # Queries Elastic + PubMed
│   ├── writer_agent.py     # Writes briefing
│   └── compliance_agent.py # UCPMP 2024 compliance check
├── tools/                  # Tool functions for agents
│   ├── mcp_servers.py      # Partner MCP server toolsets for ADK
│   ├── mongo_tools.py      # Controlled MongoDB read/write
│   ├── elastic_tools.py    # Structured Elastic search
│   ├── pubmed_tools.py     # PubMed + ClinicalTrials API
├── db/                     # Database seeding scripts
│   ├── seed_data.py        # Seeds MongoDB collections
│   └── seed_elastic.py     # Seeds Elastic index
├── config.py               # Env vars + connection strings
├── trigger.py              # MongoDB change stream listener
└── .env                    # Your credentials (git-ignored)
```
