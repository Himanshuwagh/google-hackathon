# PharmaOps Sales Agent

> Fully autonomous AI agent for pharmaceutical sales reps in India.  
> Built for the **Google Cloud Rapid Agent Hackathon** (MongoDB + Elastic partner tracks).

## What It Does

When a new doctor meeting is added to MongoDB, the agent **automatically**:

1. **Detects** the new meeting via MongoDB Change Stream
2. **Plans** an execution strategy using Gemini
3. **Retrieves** internal docs from Elastic + live evidence from PubMed/ClinicalTrials.gov
4. **Writes** personalised talking points
5. **Validates** against India's UCPMP 2024 pharmaceutical marketing law
6. **Saves** the briefing to MongoDB, creates a Google Calendar prep block, drafts a Gmail email
7. **Rep wakes up** to find everything done — no prompts, no clicks

**This is NOT a chatbot.** The agent runs end-to-end in the background.

## Tech Stack

| Component | Tool |
|---|---|
| AI Brain | Google ADK + Gemini |
| Database | MongoDB Atlas (MCP server) |
| Doc Search | Elasticsearch (MCP server) |
| Evidence | PubMed API, ClinicalTrials.gov API, OpenFDA API |
| Calendar | Google Calendar API |
| Email | Gmail API |
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
│   ├── mongo_tools.py      # MongoDB MCP read/write
│   ├── elastic_tools.py    # Elastic MCP search
│   ├── pubmed_tools.py     # PubMed + ClinicalTrials API
│   ├── gmail_tools.py      # Gmail draft creation
│   └── calendar_tools.py   # Calendar event creation
├── db/                     # Database seeding scripts
│   ├── seed_data.py        # Seeds MongoDB collections
│   └── seed_elastic.py     # Seeds Elastic index
├── config.py               # Env vars + connection strings
├── trigger.py              # MongoDB change stream listener
└── .env                    # Your credentials (git-ignored)
```
