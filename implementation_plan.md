# Vibe-Coding Implementation Plan — Phased Prompts

## The Method: "Build → Verify → Next" Loop

**Rule:** Never move to Phase N+1 until Phase N runs without errors.

```
For each phase:
  1. Give the LLM the prompt below (copy-paste)
  2. Run the code
  3. Fix any errors (paste error back to LLM)
  4. Verify the checkpoint passes
  5. Git commit
  6. Move to next phase
```

> [!IMPORTANT]
> **Tech constraints (hackathon rules):** Google ADK, Gemini models, Google Cloud, Elastic, MongoDB only. No LangChain, no OpenAI, no competing cloud services.

---

## Project Structure (Target)

```
pharma-briefing-agent/
├── agent/
│   ├── __init__.py
│   ├── main_agent.py          # SequentialAgent orchestrator
│   ├── planner_agent.py       # Step 1: reads meeting, builds plan
│   ├── retriever_agent.py     # Step 2: queries Elastic + PubMed
│   ├── writer_agent.py        # Step 3: writes brief per drug
│   └── compliance_agent.py    # Step 4: checks rules, loops
├── tools/
│   ├── __init__.py
│   ├── mongo_tools.py         # MongoDB read/write functions
│   ├── elastic_tools.py       # Elastic search functions
│   ├── pubmed_tools.py        # PubMed + ClinicalTrials API
│   ├── gmail_tools.py         # Gmail draft creation
│   └── calendar_tools.py      # Google Calendar event creation
├── db/
│   ├── seed_data.py           # Seed MongoDB with demo data
│   └── seed_elastic.py        # Seed Elastic indices with demo docs
├── config.py                  # All env vars, connection strings
├── trigger.py                 # MongoDB change stream listener
├── requirements.txt
├── .env
└── README.md
```

---

## Phase 0: Environment Setup
**Goal:** Python env + all dependencies installed and verified

### Prompt:
```
I'm building a pharma sales rep AI briefing agent for a hackathon.
Tech stack: Google ADK (google-adk), Gemini models, Elasticsearch,
MongoDB, Gmail API, Google Calendar API. Python 3.10+.

Create:
1. requirements.txt with these exact packages:
   - google-adk
   - pymongo
   - elasticsearch
   - google-api-python-client
   - google-auth-oauthlib
   - python-dotenv
   - requests

2. .env.example with placeholders for:
   - GOOGLE_API_KEY
   - MONGODB_URI
   - ELASTIC_CLOUD_ID
   - ELASTIC_API_KEY
   - GMAIL_CREDENTIALS_PATH
   - GOOGLE_CALENDAR_ID

3. config.py that loads all env vars with validation
   (raise clear error if any are missing)

Do NOT create any agents or tools yet. Just the foundation.
```

### ✅ Checkpoint: `python config.py` prints all config keys loaded

---

## Phase 1: MongoDB Schemas + Seed Data
**Goal:** All 6 collections created and seeded with demo data

### Prompt:
```
I have a pharma AI briefing agent project. Create db/seed_data.py
that connects to MongoDB (using config.py MONGODB_URI) and seeds
these collections with realistic demo data:

1. reps — 1 rep: Rakesh Sharma, territory Mumbai West, cardiology
2. hcps — 2 doctors:
   - Dr. Ananya Mehta (cardiologist, cost-sensitive, relationship_score 7)
   - Dr. Vikram Patel (nephrologist, prefers-generics, relationship_score 5)
3. meetings — 2 meetings (one single-drug, one multi-drug):
   - mtg_001: Rakesh → Dr. Mehta, drug_ids: ["drug_cardivex_500"]
   - mtg_002: Rakesh → Dr. Patel, drug_ids: ["drug_cardivex_500", "drug_renova_250"]
   Both with status: "scheduled", agent_triggered: false
4. drugs — 2 drugs:
   - drug_cardivex_500: ACE inhibitor, hypertension + heart failure
   - drug_renova_250: ARB, heart failure + CKD
5. compliance_rules — 5 rules (blocker severity):
   - Efficacy claims need n>=300 study
   - No comparative superiority without head-to-head trial
   - No off-label mentions
   - Safety profile must accompany benefits
   - No absolute claims (always, best, most effective)
6. agent_runs — empty collection, just create it

Use upsert so the script is idempotent (can run multiple times).
Print confirmation after each collection is seeded.
```

### ✅ Checkpoint: `python db/seed_data.py` → prints 6 confirmations, `mongosh` shows all docs

---

## Phase 2: MongoDB Tool Functions
**Goal:** Pure Python functions that read/write MongoDB — no agents yet

### Prompt:
```
Create tools/mongo_tools.py with these pure Python functions.
Each function must have a clear docstring with Args/Returns
(Google ADK uses docstrings to understand tools).
Each must return a dict. No default parameter values.

Functions:
1. get_meeting(meeting_id: str) -> dict
   Fetches meeting doc, joins with rep + hcp + drug profiles.
   Returns combined context object.

2. get_compliance_rules() -> dict
   Returns all active compliance rules as a list.

3. save_briefing(briefing_data: str) -> dict
   Parses briefing_data JSON string, saves to briefings collection.
   Returns {"status": "saved", "briefing_id": "..."}.

4. update_meeting_status(meeting_id: str, status: str,
   briefing_id: str) -> dict
   Updates meeting: status, briefing_ready, agent_triggered flags.

Use pymongo and config.py for connection.
Add a __main__ block that tests get_meeting("mtg_001") and prints result.
```

### ✅ Checkpoint: `python tools/mongo_tools.py` → prints full meeting context with joined data

---

## Phase 3: Elasticsearch Indices + Seed Data
**Goal:** 3 Elastic indices created, seeded, and queryable

### Prompt:
```
Create db/seed_elastic.py that connects to Elasticsearch
(using config.py ELASTIC_CLOUD_ID and ELASTIC_API_KEY) and:

1. Creates index "idx_company_docs" with mapping:
   - doc_id (keyword), doc_type (keyword), drug_id (keyword)
   - therapeutic_area (keyword), title (text), content (text)
   - tags (keyword)
   Seeds 4 docs: Cardivex datasheet, Cardivex India trial summary,
   Renova datasheet, Renova HF outcomes summary.
   Use realistic pharma content (3-4 sentences each).

2. Creates index "idx_crm_memory" with mapping:
   - doc_id (keyword), hcp_id (keyword), rep_id (keyword)
   - drug_ids (keyword), date (date), content (text)
   Seeds 3 past visit notes for Dr. Mehta, 2 for Dr. Patel.

3. Creates index "idx_competitive_intel" with mapping:
   - doc_id (keyword), competitor_drug (keyword)
   - therapeutic_area (keyword), our_drug_ids (keyword)
   - content (text), weakness_tags (keyword)
   Seeds 2 docs: Lisinopril competitor brief, Sacubitril competitor brief.

Use delete_by_query + bulk index for idempotency.
Print doc counts per index after seeding.

NOTE: Do NOT use dense_vector fields yet. We will add embeddings
in a later phase. Start with BM25 text search only.
```

### ✅ Checkpoint: `python db/seed_elastic.py` → prints doc counts (4, 5, 2)

---

## Phase 4: Elasticsearch Tool Functions
**Goal:** Search functions that query each index correctly

### Prompt:
```
Create tools/elastic_tools.py with these pure Python functions.
Each returns a dict. Clear docstrings. No default parameters.

1. search_company_docs(query_text: str, drug_id: str) -> dict
   Searches idx_company_docs using bool query:
   - must: match on content field with query_text
   - filter: term on drug_id
   Returns top 5 results with doc_id, title, content snippet.

2. search_crm_memory(hcp_id: str) -> dict
   Searches idx_crm_memory:
   - filter: term on hcp_id
   - sort: date descending
   Returns last 5 interaction notes.

3. search_competitive_intel(query_text: str,
   therapeutic_area: str) -> dict
   Searches idx_competitive_intel using bool query:
   - must: match on content
   - filter: term on therapeutic_area
   Returns top 3 results.

Use elasticsearch-py client. Add __main__ block that tests
all 3 functions with sample queries and prints results.
```

### ✅ Checkpoint: `python tools/elastic_tools.py` → prints results from all 3 indices

---

## Phase 5: External API Tool Functions
**Goal:** PubMed + ClinicalTrials.gov functions working

### Prompt:
```
Create tools/pubmed_tools.py with these functions:

1. search_pubmed(query: str, max_results: str) -> dict
   Uses NCBI E-utilities API:
   - esearch to get PMIDs
   - efetch to get title + abstract for top results
   Returns list of {pmid, title, abstract_snippet, pub_date}.
   Handle API errors gracefully — return empty results, not crash.

2. search_clinical_trials(query: str, max_results: str) -> dict
   Uses ClinicalTrials.gov v2 API:
   - GET https://clinicaltrials.gov/api/v2/studies
   - filter.overallStatus=COMPLETED
   Returns list of {nctId, briefTitle, phase, enrollment}.
   Handle API errors gracefully.

Both functions: no default params, return dict, clear docstrings.
Add __main__ block testing both with "ACE inhibitor hypertension".
```

### ✅ Checkpoint: `python tools/pubmed_tools.py` → prints real PubMed + ClinicalTrials results

---

## Phase 6: First ADK Agent — The Planner
**Goal:** Single LlmAgent that reads meeting context and outputs a plan

### Prompt:
```
Create agent/planner_agent.py using Google ADK.

This agent:
- Name: "MeetingPlanner"
- Model: "gemini-2.5-flash"
- Tools: [get_meeting] from tools/mongo_tools.py
- output_key: "execution_plan"
- Instruction: (see below)

Instruction for the agent:
"You are a pharma sales briefing planner. Given a meeting_id,
use the get_meeting tool to fetch the full meeting context.
Then output a structured JSON plan with:
- hcp_name, hcp_specialty, known_objections
- For each drug in drug_ids:
  - drug_name, drug_class
  - company_doc_query (what to search in internal docs)
  - competitive_query (what to search for competitor intel)
  - pubmed_query (what to search on PubMed)
- personalization_notes (based on relationship_score, objections)
Output ONLY the JSON plan, no other text."

Also create a simple test script that:
1. Creates an InMemorySessionService
2. Creates a Runner with this agent
3. Sends "meeting_id: mtg_001" as user message
4. Prints the agent's response

Use this pattern:
  from google.adk.agents import LlmAgent
  from google.adk.runners import Runner
  from google.adk.sessions import InMemorySessionService
```

### ✅ Checkpoint: Run test → agent calls get_meeting tool, outputs JSON plan

---

## Phase 7: Retriever Agent
**Goal:** Agent that takes the plan and executes all searches

### Prompt:
```
Create agent/retriever_agent.py using Google ADK.

This agent:
- Name: "InformationRetriever"
- Model: "gemini-2.5-flash"
- Tools: [search_company_docs, search_crm_memory,
          search_competitive_intel, search_pubmed,
          search_clinical_trials]
- output_key: "retrieved_context"
- Instruction:

"You are an information retriever for pharma sales briefings.
You receive an execution_plan (from the planner) in the session state.
Read the plan from {execution_plan}.

For EACH drug in the plan:
1. Call search_company_docs with the drug's company_doc_query
   and drug_id
2. Call search_competitive_intel with the competitive_query
   and therapeutic_area
3. Call search_pubmed with the pubmed_query, max_results '3'
4. Call search_clinical_trials with the pubmed_query,
   max_results '3'

Also call search_crm_memory ONCE with the hcp_id.

After all tools return, compile everything into a structured
JSON context object with sections:
- crm_memory: [...]
- per_drug: { drug_id: { company_docs, competitive_intel,
  pubmed, clinical_trials } }

Output ONLY the JSON context."

Add test script that manually sets session state with a
sample execution_plan and runs this agent.
```

### ✅ Checkpoint: Agent makes all tool calls and returns assembled context JSON

---

## Phase 8: Brief Writer Agent
**Goal:** Agent that writes the actual briefing from retrieved context

### Prompt:
```
Create agent/writer_agent.py using Google ADK.

This agent:
- Name: "BriefWriter"
- Model: "gemini-2.5-pro" (use Pro for quality writing)
- No tools needed — pure LLM reasoning
- output_key: "draft_brief"
- Instruction:

"You are a pharma sales briefing writer. You receive
retrieved_context from {retrieved_context} and the
execution_plan from {execution_plan}.

Write a briefing with these sections for EACH drug:
1. Key Talking Points (3-4 bullet points per drug)
   - Each point must cite a specific source (PubMed PMID
     or internal doc_id)
   - Include specific numbers (n=, p-value, % reduction)
2. Known Objections & Responses
   - Based on the doctor's known_objections from the plan
   - Use competitive intel to build counter-arguments
3. Cross-Drug Notes (if multi-drug meeting)
   - How to transition between drugs in conversation

Also write:
- draft_email_subject (one line)
- draft_email_body (3-4 paragraph professional email)

Output as structured JSON with drug_sections, cross_drug_notes,
draft_email_subject, draft_email_body."
```

### ✅ Checkpoint: Agent outputs a realistic briefing JSON with citations

---

## Phase 9: Compliance Checker Agent
**Goal:** Agent that validates brief against rules, flags violations

### Prompt:
```
Create agent/compliance_agent.py using Google ADK.

This agent:
- Name: "ComplianceChecker"
- Model: "gemini-2.5-flash" (cheaper, faster for rule checking)
- Tools: [get_compliance_rules] from tools/mongo_tools.py
- output_key: "compliance_result"
- Instruction:

"You are a pharma compliance checker. You receive a draft
briefing from {draft_brief}.

Step 1: Call get_compliance_rules to load all active rules.
Step 2: Check EVERY talking point and email body against
EVERY rule.
Step 3: Output a JSON result:
{
  'passed': true/false,
  'flags': [
    {
      'rule_id': '...',
      'offending_text': '...',
      'reason': '...',
      'severity': 'blocker'
    }
  ],
  'clean_brief': '...'  // the brief with fixes applied
                         // if passed=true, same as input
}

If any blocker rule is violated, set passed=false.
If passed=false, rewrite ONLY the offending sections to fix
the violations, and include the corrected version in
clean_brief."

IMPORTANT: This agent self-corrects in one pass. The
orchestrator will handle retry loops.
```

### ✅ Checkpoint: Feed it a brief with "Cardivex is the BEST drug" → it flags rule_005

---

## Phase 10: Google Calendar + Gmail Tools
**Goal:** Calendar and Gmail integration functions

### Prompt:
```
Create two files:

tools/calendar_tools.py:
- create_prep_event(rep_calendar_id: str, hcp_name: str,
  drug_names: str, meeting_datetime: str,
  key_points: str) -> dict
  Creates a 15-min calendar event BEFORE the meeting time.
  Uses Google Calendar API v3.
  Returns {status, event_id} or {status: "error", message}.

tools/gmail_tools.py:
- create_draft_email(subject: str, body: str,
  recipient_hint: str) -> dict
  Creates a draft email in the rep's Gmail.
  Uses Gmail API v1.
  Returns {status, draft_id} or {status: "error", message}.

Both should:
- Use service account or OAuth2 credentials from
  config.GMAIL_CREDENTIALS_PATH
- Handle API failures gracefully (return error dict, never crash)
- Have clear docstrings for ADK tool compatibility

Add __main__ test blocks that create a test event and draft.
```

### ✅ Checkpoint: Test calendar event appears in Google Calendar, draft appears in Gmail

---

## Phase 11: The Orchestrator — SequentialAgent
**Goal:** Wire all 4 agents into a single pipeline

### Prompt:
```
Create agent/main_agent.py that orchestrates the full pipeline.

Use Google ADK SequentialAgent to run agents in order:
1. MeetingPlanner (from planner_agent.py)
2. InformationRetriever (from retriever_agent.py)
3. BriefWriter (from writer_agent.py)
4. ComplianceChecker (from compliance_agent.py)

After the SequentialAgent completes, add a final
"ActionExecutor" LlmAgent that:
- Reads compliance_result from {compliance_result}
- If passed: calls save_briefing, update_meeting_status,
  create_prep_event, create_draft_email
- If not passed after compliance: saves with
  compliance_status="needs_review"
- Tools: [save_briefing, update_meeting_status,
  create_prep_event, create_draft_email]

The full pipeline:
  pipeline = SequentialAgent(
      name="PharmaBriefingPipeline",
      sub_agents=[planner, retriever, writer,
                  compliance_checker, action_executor]
  )

Create a run_pipeline(meeting_id: str) function that:
1. Creates InMemorySessionService
2. Creates Runner with the pipeline
3. Sends meeting_id as initial message
4. Returns the final briefing

Add __main__ that runs pipeline for "mtg_001".
```

### ✅ Checkpoint: Full pipeline runs end-to-end for mtg_001, briefing saved to MongoDB

---

## Phase 12: Trigger System
**Goal:** MongoDB change stream that auto-triggers the pipeline

### Prompt:
```
Create trigger.py that:
1. Connects to MongoDB
2. Opens a change stream on the 'meetings' collection
3. Watches for documents where:
   - status == "scheduled"
   - agent_triggered == false
4. When detected:
   - Immediately set agent_triggered = true (prevent re-trigger)
   - Call run_pipeline(meeting_id) from main_agent.py
   - Log result to agent_runs collection with per-step timing
5. Handle errors:
   - If pipeline fails, log error to agent_runs
   - Set meeting status to "agent_error"
   - Continue watching (don't crash)

Add a graceful shutdown on SIGINT.
Print clear logs: "Watching for new meetings..."
"Triggered pipeline for mtg_001..." etc.
```

### ✅ Checkpoint: Insert a new meeting in mongosh → agent auto-triggers and produces briefing

---

## Phase 13: Demo Polish
**Goal:** Everything works for a live demo

### Prompt:
```
Create a simple demo script demo.py that:

1. Prints "=== Pharma AI Briefing Agent Demo ==="
2. Shows current meetings in MongoDB (status: scheduled)
3. Asks user to pick a meeting_id (or creates a fresh one)
4. Runs the full pipeline with visible step-by-step logging:
   - "Step 1: Planning... ✓ (1.2s)"
   - "Step 2: Retrieving from 3 sources... ✓ (3.4s)"
   - "Step 3: Writing brief... ✓ (2.8s)"
   - "Step 4: Compliance check... ✓ passed (1.1s)"
   - "Step 5: Actions... Calendar ✓ Gmail ✓ MongoDB ✓"
5. Prints the final briefing in a readable format
6. Shows total time elapsed

Keep it simple — this is for a hackathon demo video.
```

### ✅ Checkpoint: Full demo runs in under 60 seconds with clear output

---

## Prompt Tips to Reduce Errors

| Tip | Why |
|---|---|
| **Always paste your existing file structure** at the top of each prompt | LLM needs to know what exists |
| **Paste the exact import paths** you're using | Prevents `import from wrong_module` errors |
| **Include the previous phase's output format** | "Phase 6 outputs JSON like: {this shape}" |
| **One file per prompt** (mostly) | Multi-file prompts cause cross-file errors |
| **Paste the error, not "it doesn't work"** | Full traceback = instant fix |
| **Commit after each phase** | Git reset if a phase goes sideways |
| **Test tools BEFORE agents** | If tool is broken, agent debugging is hell |

## Error Recovery Template
When something breaks, use this prompt:
```
I'm getting this error:
[paste full traceback]

Here is the file that's failing:
[paste full file]

Here are the files it imports from:
[paste relevant imports]

Fix ONLY the error. Do not refactor or change anything else.
```

---

## Execution Order Summary

```
Phase 0:  pip install + config           (30 min)
Phase 1:  MongoDB seed data              (30 min)
Phase 2:  MongoDB tool functions         (30 min)
Phase 3:  Elastic indices + seed         (45 min)
Phase 4:  Elastic tool functions         (30 min)
Phase 5:  PubMed/ClinicalTrials tools    (30 min)
── MILESTONE: All tools work standalone ──
Phase 6:  Planner agent                  (45 min)
Phase 7:  Retriever agent               (45 min)
Phase 8:  Writer agent                  (30 min)
Phase 9:  Compliance agent              (45 min)
── MILESTONE: All agents work standalone ──
Phase 10: Calendar + Gmail tools         (45 min)
Phase 11: SequentialAgent orchestrator   (60 min)
Phase 12: Change stream trigger          (30 min)
Phase 13: Demo polish                    (30 min)
── TOTAL: ~8-9 hours ──
```
