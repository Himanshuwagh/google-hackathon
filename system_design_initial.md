# Pharma Sales Rep AI Briefing Agent — Full System Design

---

## 1. High-Level Architecture

```mermaid
graph TB
    subgraph TRIGGER["⚡ Trigger Layer"]
        CS[MongoDB Change Stream<br/>meetings collection]
        SCHED[Fallback: Nightly Cron<br/>00:00 IST]
    end

    subgraph ORCHESTRATOR["🧠 Orchestrator Layer (Google ADK)"]
        PLANNER[Gemini — Planner Agent<br/>Reads meeting, decomposes task]
        EXECUTOR[Gemini — Executor Agent<br/>Runs tools, drafts brief]
        COMPLIANCE[Gemini — Compliance Agent<br/>Checks rules, flags violations]
    end

    subgraph RETRIEVAL["🔍 Retrieval Layer"]
        ELASTIC[Elasticsearch<br/>Hybrid BM25 + kNN RRF]
        MONGO_READ[MongoDB<br/>Structured Filter Lookup]
        PUBMED[PubMed API<br/>ncbi.nlm.nih.gov]
        CTGOV[ClinicalTrials.gov API]
    end

    subgraph DATASTORES["🗄️ Data Stores"]
        subgraph MONGO["MongoDB Atlas"]
            M1[(meetings)]
            M2[(reps)]
            M3[(hcps)]
            M4[(drugs)]
            M5[(briefings)]
            M6[(compliance_rules)]
        end
        subgraph ES["Elasticsearch"]
            E1[(drug_knowledge index)]
            E2[(competitive_intel index)]
            E3[(hcp_memory index)]
        end
    end

    subgraph ACTIONS["⚙️ Action Layer (Tools)"]
        GCAL[Google Calendar API<br/>Create prep block]
        GMAIL[Gmail API<br/>Create draft]
        MONGO_WRITE[MongoDB Write<br/>Save briefing]
    end

    subgraph UI["👁️ Rep-Facing Layer"]
        DASH[Rep Dashboard<br/>Web App]
        NOTIF[Push Notification<br/>Brief ready]
    end

    CS -->|new meeting event| PLANNER
    SCHED -->|scheduled meetings| PLANNER
    PLANNER --> EXECUTOR
    EXECUTOR --> ELASTIC
    EXECUTOR --> MONGO_READ
    EXECUTOR --> PUBMED
    EXECUTOR --> CTGOV
    ELASTIC --> E1
    ELASTIC --> E2
    ELASTIC --> E3
    MONGO_READ --> M1
    MONGO_READ --> M2
    MONGO_READ --> M3
    MONGO_READ --> M4
    EXECUTOR --> COMPLIANCE
    COMPLIANCE --> M6
    COMPLIANCE -->|flagged| EXECUTOR
    COMPLIANCE -->|passed| ACTIONS
    ACTIONS --> GCAL
    ACTIONS --> GMAIL
    ACTIONS --> MONGO_WRITE
    MONGO_WRITE --> M5
    MONGO_WRITE -->|status: briefing_ready| M1
    M5 --> DASH
    DASH --> NOTIF
```

---

## 2. Complete Data Model (Low-Level Schema)

### MongoDB Collections

```mermaid
erDiagram
    MEETINGS {
        string meeting_id PK
        string rep_id FK
        string hcp_id FK
        array drug_ids FK
        string primary_drug_id FK
        string meeting_focus
        datetime date
        string location
        string status
        bool agent_triggered
        string briefing_id FK
        bool rep_reviewed
    }

    REPS {
        string rep_id PK
        string name
        string email
        string google_calendar_id
        string territory
        string experience_years
        string preferred_brief_length
        float relationship_score
    }

    HCPS {
        string hcp_id PK
        string name
        string specialty
        array known_objections
        string last_visit_date
        string last_visit_note
        float relationship_score
        bool address_cost_concern
        string preferred_brief_style
    }

    DRUGS {
        string drug_id PK
        string brand_name
        string generic_name
        string drug_class
        array indications
        array contraindications
        array pubmed_search_terms
        array elastic_doc_tags
        array approved_claims
    }

    BRIEFINGS {
        string brief_id PK
        string meeting_id FK
        string hcp_id FK
        string rep_id FK
        datetime generated_at
        string compliance_status
        int compliance_loops
        object drug_sections
        string cross_drug_notes
        array supporting_evidence
        string draft_email_subject
        string draft_email_body
        string gmail_draft_id
        string calendar_event_id
        object hcp_context_used
    }

    COMPLIANCE_RULES {
        string rule_id PK
        string category
        string rule_text
        string severity
        string action
    }

    MEETINGS ||--|| REPS : "has"
    MEETINGS ||--|| HCPS : "with"
    MEETINGS }|--|{ DRUGS : "covers"
    MEETINGS ||--o| BRIEFINGS : "produces"
    HCPS ||--o{ BRIEFINGS : "referenced_in"
```

### Detailed Schema — Key Collections

```json
// meetings — full schema
{
  "_id": "mtg_001",
  "rep_id": "rep_rakesh_sharma",
  "hcp_id": "hcp_ananya_mehta",
  "drug_ids": ["drug_cardivex_500", "drug_renova_250"],
  "primary_drug_id": "drug_cardivex_500",
  "meeting_focus": "cardiology",
  "date": "2025-06-10T10:00:00",
  "location": "Kokilaben Hospital, Mumbai",
  "duration_mins": 15,
  "status": "scheduled | briefing_ready | completed",
  "agent_triggered": false,
  "briefing_id": null,
  "rep_reviewed": false,
  "created_at": "2025-06-09"
}

// briefings — full schema (multi-drug)
{
  "_id": "brief_mtg001",
  "meeting_id": "mtg_001",
  "hcp_id": "hcp_ananya_mehta",
  "rep_id": "rep_rakesh_sharma",
  "generated_at": "2025-06-09T02:14:00Z",
  "compliance_status": "passed",
  "compliance_loops": 2,
  "drug_sections": {
    "drug_cardivex_500": {
      "talking_points": ["Cardivex reduces systolic BP by 12mmHg (CARDIO-PROTECT, n=1200, p<0.001)"],
      "compliance_status": "passed",
      "compliance_loops": 2,
      "supporting_evidence": [
        {"source": "PubMed", "pmid": "38291045", "relevance": "Primary efficacy"},
        {"source": "ClinicalTrials", "nctId": "NCT05123456"}
      ]
    },
    "drug_renova_250": {
      "talking_points": ["Renova reduces HbA1c by 1.2% at 24 weeks (RENOVA-DIAB, n=800)"],
      "compliance_status": "passed",
      "compliance_loops": 1,
      "supporting_evidence": []
    }
  },
  "cross_drug_notes": "Lead with Cardivex on BP. Renova only if diabetes co-morbidity raised.",
  "cross_drug_conflict_flags": [],
  "draft_email_subject": "Follow-up: Cardivex + Renova data for Dr. Mehta",
  "draft_email_body": "Dear Dr. Mehta, ...",
  "gmail_draft_id": "gmail_draft_xyz789",
  "calendar_event_id": "google_cal_evt_abc123",
  "hcp_context_used": {
    "known_objections": ["cost-sensitive"],
    "last_visit_note": "Positive on renal data"
  }
}
```

### Elasticsearch Indices

```json
// Index: drug_knowledge
{
  "mappings": {
    "properties": {
      "doc_id":            { "type": "keyword" },
      "doc_type":          { "type": "keyword" },
      "drug_id":           { "type": "keyword" },
      "title":             { "type": "text", "analyzer": "medical_analyzer" },
      "content":           { "type": "text", "analyzer": "medical_analyzer" },
      "content_vector":    { "type": "dense_vector", "dims": 768 },
      "therapeutic_area":  { "type": "keyword" },
      "approved_date":     { "type": "date" },
      "tags":              { "type": "keyword" }
    }
  },
  "settings": {
    "analysis": {
      "analyzer": {
        "medical_analyzer": {
          "tokenizer": "standard",
          "filter": ["lowercase", "medical_synonyms"]
        }
      }
    }
  }
}

// Index: hcp_memory
{
  "mappings": {
    "properties": {
      "doc_id":           { "type": "keyword" },
      "hcp_id":           { "type": "keyword" },
      "rep_id":           { "type": "keyword" },
      "date":             { "type": "date" },
      "content":          { "type": "text" },
      "extracted_signals": {
        "properties": {
          "objections":         { "type": "keyword" },
          "positive_responses": { "type": "keyword" },
          "samples_requested":  { "type": "boolean" }
        }
      }
    }
  }
}
```

---

## 3. Agent Execution Flow — Detailed

```mermaid
flowchart TD
    A([MongoDB Change Stream\nnew meeting inserted]) --> B

    B[Planner Agent\nGemini reads meeting object] --> C{Single or\nMulti-Drug?}

    C -->|Single| D1[Single Drug Path]
    C -->|Multi| D2[Multi-Drug Path\nSpawn parallel threads]

    D2 --> E1[Drug Thread 1\nCardivex]
    D2 --> E2[Drug Thread 2\nRenova]
    D2 --> SHARED[Shared: HCP Memory\nFetch once for all drugs]

    E1 --> F1[tool_search_elastic\ndrug_cardivex_500]
    E1 --> G1[tool_pubmed_search\ncardivex ACE inhibitor]
    E1 --> H1[tool_clinicaltrials_search\nNCT cardivex]

    E2 --> F2[tool_search_elastic\ndrug_renova_250]
    E2 --> G2[tool_pubmed_search\nrenova HbA1c]
    E2 --> H2[tool_clinicaltrials_search\nNCT renova]

    SHARED --> CRM[MongoDB Filter\nhcp_id + last 6 months]

    F1 & G1 & H1 --> CTX1[Drug 1 Context]
    F2 & G2 & H2 --> CTX2[Drug 2 Context]
    CRM --> CTX3[HCP Context]

    CTX1 & CTX2 & CTX3 --> CONFLICT[Cross-Drug Conflict Detector\nGemini reasoning step]

    CONFLICT --> CF{Conflicts\nFound?}
    CF -->|Yes| RESOLVE[Generate conflict resolution\nstrategy + warnings]
    CF -->|No| DRAFT

    RESOLVE --> DRAFT[Executor Agent\nDraft per-drug talking points\n+ cross_drug_notes]

    DRAFT --> COMP[Compliance Agent\nCheck each drug section\nagainst compliance_rules]

    COMP --> LOOP{All sections\nPass?}

    LOOP -->|Fail, attempt < 3| REWRITE[Rewrite flagged section\nwith constraint injected]
    REWRITE --> COMP

    LOOP -->|Fail, attempt = 3| HUMAN[Flag for Human Review\nStatus: needs_review]
    LOOP -->|Pass| ACTIONS

    ACTIONS --> W1[tool_write_briefing\nMongoDB briefings]
    ACTIONS --> W2[tool_create_calendar_event\nGoogle Calendar API]
    ACTIONS --> W3[tool_create_gmail_draft\nGmail API]
    ACTIONS --> W4[tool_update_meeting_status\nstatus: briefing_ready]

    W1 & W2 & W3 & W4 --> DONE([Rep wakes up\nBriefing ready 🎉])
```

---

## 4. Three-Layer Retrieval Pipeline (Low-Level)

```mermaid
flowchart LR
    subgraph INPUT["Query Input"]
        Q1["drug_id: cardivex_500\nhcp_specialty: cardiology\nmeeting_focus: cardiology"]
    end

    subgraph LAYER1["Layer 1: Structured Lookup\n(MongoDB — no ML)"]
        L1A["meetings.find(meeting_id)\nreps.find(rep_id)\nhcps.find(hcp_id)\ndrugs.find(drug_id)"]
        L1B["hcp_memory.find(\n  hcp_id: hcp_ananya_mehta,\n  date: last 6 months\n).sort(-date).limit(5)"]
    end

    subgraph LAYER2["Layer 2: Hybrid Semantic Search\n(Elasticsearch RRF)"]
        L2A["BM25 query:\nmatch: cardivex ACE inhibitor\n         renal outcome"]
        L2B["kNN query:\nvector: PubMedBERT(\n  cardivex renal protection\n)\ntop_k: 50"]
        L2C["RRF Merge\nrank_constant=60\nwindow=20"]
        L2A --> L2C
        L2B --> L2C
    end

    subgraph LAYER3["Layer 3: External APIs\n(Real-time, cached 7d)"]
        L3A["PubMed API\nGET /esearch + /efetch\nquery: ACE inhibitor\n        hypertension outcomes"]
        L3B["ClinicalTrials.gov API\nGET /query/full_studies\nquery: cardivex heart failure"]
        L3C["MongoDB Cache Check\nexpiry: 7 days TTL\nkey: drug_id + query_hash"]
    end

    subgraph MERGE["Result Merger"]
        M1["Deduplicate\nacross sources"]
        M2["MMR Reranker\nMaximal Marginal\nRelevance\ndiversity filter"]
        M3["Assembled Context\nObject → Gemini"]
    end

    Q1 --> LAYER1
    Q1 --> LAYER2
    Q1 --> LAYER3
    L3C -->|cache miss| L3A
    L3C -->|cache miss| L3B
    L3C -->|cache hit| MERGE
    L3A --> MERGE
    L3B --> MERGE
    LAYER1 --> MERGE
    L2C --> MERGE
    M1 --> M2 --> M3
```

---

## 5. Compliance Check Loop (Low-Level)

```mermaid
flowchart TD
    START([Draft talking points\nfor one drug section]) --> LOAD

    LOAD[Load compliance_rules\nfrom MongoDB\nfiltered by drug_id + severity] --> CHECK

    subgraph LOOP["Compliance Check Loop (max_attempts = 3)"]
        CHECK[Compliance Agent\nChecks each talking point\nagainst each rule]

        CHECK --> EVAL{Any rule\nviolations?}

        EVAL -->|No violations| PASS([✅ Section PASSED\nReturn to Executor])

        EVAL -->|Violations found| FLAG[Build violation report:\n- rule_id violated\n- offending_text\n- reason\n- severity: blocker/warning]

        FLAG --> SEV{All violations\nare warnings only?}

        SEV -->|Yes, warnings| WARN[Add warnings to brief\nmark: reviewed_with_warnings]
        WARN --> PASS

        SEV -->|Has blockers| CNT{attempt_count\n< 3?}

        CNT -->|Yes| INJECT[Inject constraint into prompt:\nDo not say X because rule_id\nRewrite this section]
        INJECT --> REWRITE[Executor Agent\nRewrites flagged section]
        REWRITE --> INC[attempt_count++]
        INC --> CHECK

        CNT -->|No, attempt=3| ESCALATE[❌ Flag for Human Review\nstatus: needs_manual_review\nNotify rep + manager]
    end
```

### Compliance Rules Schema (Low-Level)

```json
// compliance_rules collection
[
  {
    "rule_id": "rule_001",
    "category": "efficacy_claims",
    "rule_text": "All efficacy claims must cite a peer-reviewed study with n ≥ 500 participants.",
    "severity": "blocker",
    "action": "rewrite"
  },
  {
    "rule_id": "rule_002",
    "category": "comparative_claims",
    "rule_text": "Do not make comparative superiority claims unless a head-to-head trial is cited.",
    "severity": "blocker",
    "action": "rewrite"
  },
  {
    "rule_id": "rule_003",
    "category": "off_label",
    "rule_text": "Off-label indications must not be mentioned.",
    "severity": "blocker",
    "action": "remove"
  },
  {
    "rule_id": "rule_004",
    "category": "safety",
    "rule_text": "Safety and side-effect profile must be mentioned alongside efficacy.",
    "severity": "warning",
    "action": "append"
  },
  {
    "rule_id": "rule_005",
    "category": "absolute_claims",
    "rule_text": "No absolute claims: always, best, most effective.",
    "severity": "blocker",
    "action": "rewrite"
  }
]
```

---

## 6. Tool Function Signatures (Low-Level Design)

These are the exact tools the Gemini agent has access to:

```python
# --- RETRIEVAL TOOLS ---

def tool_search_elastic(
    drug_id: str,
    query: str,
    doc_types: list[str],         # ["drug_datasheet", "competitor_brief"]
    therapeutic_area: str,
    top_k: int = 10
) -> list[ElasticDocument]:
    """Hybrid BM25 + kNN search with RRF merge. Uses PubMedBERT embeddings."""

def tool_get_hcp_memory(
    hcp_id: str,
    rep_id: str,
    lookback_months: int = 6,
    limit: int = 5
) -> list[InteractionNote]:
    """Structured MongoDB filter — NOT semantic search. Returns most recent notes."""

def tool_pubmed_search(
    query: str,
    drug_id: str,
    max_results: int = 5,
    use_cache: bool = True,           # TTL: 7 days
    cache_key_hash: str = None
) -> list[PubMedArticle]:
    """Calls NCBI eSearch + eFetch. Extracts: title, abstract, pmid, pub_date."""

def tool_clinicaltrials_search(
    query: str,
    drug_id: str,
    max_results: int = 5,
    use_cache: bool = True
) -> list[ClinicalTrial]:
    """Calls ClinicalTrials.gov v2 API. Extracts: NCT ID, status, outcomes."""

# --- AGENT TOOLS ---

def tool_detect_cross_drug_conflicts(
    drug_contexts: dict[str, DrugContext],   # drug_id → retrieved context
    hcp_context: HCPContext
) -> CrossDrugConflictReport:
    """
    Gemini reasoning step. Detects:
    - Positioning conflicts (both drugs for same indication)
    - Clinical interaction conflicts (contraindicated co-prescription)
    - Compliance conflicts (off-label risk from combined context)
    Returns: conflict_flags[], resolution_strategy, conversation_order
    """

def tool_check_compliance(
    drug_id: str,
    talking_points: list[str],
    supporting_evidence: list[Evidence],
    attempt_number: int
) -> ComplianceResult:
    """
    Compliance Agent checks each point against compliance_rules.
    Returns: passed bool, violations[], rewrite_instructions
    """

# --- ACTION TOOLS ---

def tool_write_briefing(
    briefing: BriefingDocument
) -> str:
    """Writes to MongoDB briefings collection. Returns brief_id."""

def tool_update_meeting_status(
    meeting_id: str,
    status: str,                    # "briefing_ready" | "needs_review"
    briefing_id: str
) -> bool:
    """Patches meetings document."""

def tool_create_calendar_event(
    rep_calendar_id: str,
    meeting_datetime: datetime,
    hcp_name: str,
    brief_link: str
) -> str:
    """
    Creates 15-min prep block BEFORE meeting_datetime.
    Attaches brief link in description.
    Returns: google calendar event_id.
    """

def tool_create_gmail_draft(
    rep_email: str,
    hcp_email: str,
    subject: str,
    body: str,
    brief_link: str
) -> str:
    """Creates Gmail draft. Returns gmail_draft_id."""

def tool_notify_error(
    meeting_id: str,
    rep_id: str,
    stage: str,
    error_message: str
) -> None:
    """Push error to rep dashboard + optional Slack webhook. Never fails silently."""
```

---

## 7. Error Handling & Observability

```mermaid
stateDiagram-v2
    [*] --> triggered: Meeting added to DB

    triggered --> planning: Planner Agent reads context
    planning --> retrieving: Tools dispatched

    retrieving --> drafting: All retrieval complete
    retrieving --> partial_retrieval: External API failed

    partial_retrieval --> drafting: Use cached data\nor internal only

    drafting --> compliance_check: Draft complete
    compliance_check --> compliance_check: Violation found\nattempt < 3 — rewrite

    compliance_check --> writing_outputs: All passed
    compliance_check --> needs_review: 3 attempts failed

    writing_outputs --> mongo_write: Save briefing
    writing_outputs --> calendar_write: Create prep block
    writing_outputs --> gmail_write: Create draft

    mongo_write --> complete: OK
    calendar_write --> complete: OK
    gmail_write --> complete: OK

    mongo_write --> error_state: API Error
    calendar_write --> error_state: API Error
    gmail_write --> error_state: API Error

    complete --> [*]: Rep notified via dashboard

    needs_review --> rep_notified_review: Push to dashboard\n"Manual review needed"
    error_state --> rep_notified_error: Push to dashboard\n+ log to observability

    rep_notified_review --> [*]
    rep_notified_error --> [*]
```

### Observability Schema (Every Agent Step Logged)

```json
{
  "run_id": "run_20250609_mtg001",
  "meeting_id": "mtg_001",
  "start_time": "2025-06-09T02:00:00Z",
  "end_time": "2025-06-09T02:14:22Z",
  "total_duration_ms": 862000,
  "steps": [
    { "step": "planning",      "status": "ok", "duration_ms": 2100 },
    { "step": "elastic_search","status": "ok", "duration_ms": 340,  "docs_retrieved": 8 },
    { "step": "pubmed",        "status": "ok", "duration_ms": 1800, "articles": 3 },
    { "step": "clinicaltrials","status": "ok", "duration_ms": 2200, "trials": 2 },
    { "step": "cross_drug_conflict_check", "status": "ok", "conflicts_found": 0 },
    { "step": "drafting",      "status": "ok", "duration_ms": 4200 },
    { "step": "compliance_1",  "status": "fail","violations": ["rule_002"] },
    { "step": "compliance_2",  "status": "pass","duration_ms": 3100 },
    { "step": "mongo_write",   "status": "ok" },
    { "step": "calendar_write","status": "ok" },
    { "step": "gmail_write",   "status": "ok" }
  ],
  "final_status": "briefing_ready",
  "compliance_loops": 2,
  "drugs_covered": ["drug_cardivex_500", "drug_renova_250"]
}
```

---

## 8. Complete System At a Glance

```
INFRASTRUCTURE
├── MongoDB Atlas          → Operational store (structured data)
│   ├── meetings           → The trigger + status tracker
│   ├── reps               → Rep profile + Google credentials
│   ├── hcps               → Doctor profile + objections
│   ├── drugs              → Drug catalog + search hints
│   ├── briefings          → Agent output (written by agent)
│   └── compliance_rules   → FDA + company rules (read by agent)
│
├── Elasticsearch          → Knowledge retrieval (unstructured)
│   ├── drug_knowledge     → Drug datasheets, clinical summaries
│   ├── competitive_intel  → Competitor briefings
│   └── hcp_memory         → Past interaction notes
│
├── External APIs
│   ├── PubMed             → Latest clinical trial data
│   ├── ClinicalTrials.gov → Trial registry search
│   ├── Google Calendar    → Create prep events
│   └── Gmail              → Create draft emails
│
AGENT RUNTIME (Google ADK)
├── Planner Agent          → Reads meeting, decomposes task per drug
├── Executor Agent         → Calls tools, retrieves, drafts brief
└── Compliance Agent       → Self-checks output, loops until passed

RETRIEVAL STRATEGY
├── Structured data        → MongoDB filter (no ML needed)
├── Unstructured text      → Elastic BM25 + kNN RRF (PubMedBERT)
└── External literature    → Direct API + 7-day MongoDB cache

MULTI-DRUG ADDITION
├── Parallel retrieval per drug
├── Cross-drug conflict detection (positioning + clinical + compliance)
└── Unified brief with per-drug sections + cross_drug_notes

ERROR HANDLING
├── External API fails     → Use cache or internal-only mode
├── Compliance > 3 loops   → Escalate to human review
├── Action API fails       → Log + notify rep dashboard (never silent)
└── Full observability log → Every step duration + status
```
