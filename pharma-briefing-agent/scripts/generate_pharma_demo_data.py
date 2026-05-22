#!/usr/bin/env python3
"""Generate realistic CardioGlyde / OncoTarget pharma demo data (May–June 2026)."""

import json
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ── New HCP personas ─────────────────────────────────────────────
NEW_HCPS = [
    {
        "_id": "hcp_sarah_chen",
        "name": "Dr. Sarah Chen",
        "specialty": "Medical Oncology",
        "hospital": "Tata Memorial Centre",
        "city": "Mumbai",
        "preferred_language": "English",
        "prescribing_focus": [
            "EGFR-mutated NSCLC",
            "clinical trial enrollment",
            "precision oncology"
        ],
        "known_objections": [
            "rejects marketing language — demands peer-reviewed data",
            "requires P-values and confidence intervals for all efficacy claims",
            "skeptical of oral TKIs without head-to-head IV comparison"
        ],
        "persona_type": "kol_academic",
        "preferred_brief_style": "scientific_deep_dive",
        "last_visited": "2026-05-04",
        "relationship_score": 6,
        "territory_rep_id": "rep_rakesh_sharma",
    },
    {
        "_id": "hcp_marcus_thorne",
        "name": "Dr. Marcus Thorne",
        "specialty": "Primary Care / Family Medicine",
        "hospital": "Lilavati Hospital",
        "city": "Mumbai",
        "preferred_language": "English",
        "prescribing_focus": [
            "type 2 diabetes",
            "obesity",
            "hypertension",
            "high-volume chronic disease management"
        ],
        "known_objections": [
            "extremely time-constrained — max 5 minutes per rep visit",
            "patients resist injectables",
            "needs simple dosing and PAP paperwork pre-filled"
        ],
        "persona_type": "busy_high_volume_prescriber",
        "preferred_brief_style": "three_bullet_summary",
        "last_visited": "2026-05-04",
        "relationship_score": 7,
        "territory_rep_id": "rep_rakesh_sharma",
    },
    {
        "_id": "hcp_emily_rodriguez",
        "name": "Dr. Emily Rodriguez",
        "specialty": "Endocrinology",
        "hospital": "Manipal Hospital",
        "city": "Bangalore",
        "preferred_language": "English",
        "prescribing_focus": [
            "type 2 diabetes",
            "GLP-1 therapy",
            "obesity management"
        ],
        "known_objections": [
            "currently prescribes MetaboMax to ~80% of eligible T2DM patients",
            "values oral convenience over injectable efficacy",
            "nurses influence formulary preference toward MetaboMax"
        ],
        "persona_type": "competitor_loyalist",
        "preferred_brief_style": "objection_handling",
        "last_visited": "2026-05-06",
        "relationship_score": 5,
        "territory_rep_id": "rep_priya_nair",
    },
    {
        "_id": "hcp_james_wilson",
        "name": "Dr. James Wilson",
        "specialty": "Cardiology",
        "hospital": "Max Super Speciality Hospital",
        "city": "New Delhi",
        "preferred_language": "English",
        "prescribing_focus": [
            "ASCVD risk reduction",
            "heart failure with preserved EF",
            "diabetic cardiomyopathy"
        ],
        "known_objections": [
            "highly risk-averse — prioritizes safety over efficacy",
            "concerned about GLP-1 GI adverse events and pancreatitis signals",
            "requires explicit GI management and titration protocols before prescribing"
        ],
        "persona_type": "safety_first_skeptic",
        "preferred_brief_style": "safety_focused",
        "last_visited": "2026-05-05",
        "relationship_score": 4,
        "territory_rep_id": "rep_arjun_desai",
    },
    {
        "_id": "hcp_michael_foster",
        "name": "Dr. Michael Foster",
        "specialty": "Medical Oncology",
        "hospital": "Fortis Memorial Research Institute",
        "city": "Gurgaon",
        "preferred_language": "English",
        "prescribing_focus": [
            "community NSCLC",
            "palliative-quality regimens",
            "IV chemotherapy familiarity"
        ],
        "known_objections": [
            "long-standing VenaChemo prescriber — trusts infusion-center monitoring",
            "worried oral OncoTarget reduces visit adherence visibility",
            "concerned about rash management without infusion-suite nursing support"
        ],
        "persona_type": "legacy_iv_loyalist",
        "preferred_brief_style": "quality_of_life_comparison",
        "last_visited": "2026-05-07",
        "relationship_score": 5,
        "territory_rep_id": "rep_arjun_desai",
    },
]

VISIT_STORIES = {
    "hcp_sarah_chen": {
        "rep_id": "rep_rakesh_sharma",
        "primary_drug": "drug_oncotarget",
        "tags": ["oncotarget", "oncology", "egfr", "nsclc"],
        "visits": [
            (
                "2026-02-18",
                "Visit 1 — Initial Introduction (OncoTarget)",
                "First formal call with Dr. Chen at Tata Memorial thoracic oncology conference room. 12 minutes. Introduced OncoTarget as oral EGFR TKI for exon 19/L858R NSCLC. She was neutral — listened without interrupting but said she already uses established TKIs and does not switch on rep slides. Left ONCO-STAR trial design one-pager and EGFR reflex testing workflow card. She asked zero marketing questions; only asked whether we have exon 19 vs L858R subgroup PFS breakdown. Sentiment: Neutral. No samples requested.",
            ),
            (
                "2026-04-03",
                "Visit 2 — Subgroup Data Objection",
                "Second meeting in her office. 18 minutes. She raised the core objection: 'Show me hazard ratios by mutation subtype, not pooled ITT.' Specifically challenged whether oral convenience claims are irrelevant to her academic practice. She explicitly said she hates marketing fluff and will not read brochures without PMID citations. Requested full statistical appendix from ONCO-STAR. Competitor context: she mentioned hospital formulary still favors legacy IV options for frail patients. Sentiment: Skeptical but intellectually engaged.",
            ),
            (
                "2026-05-04",
                "Visit 3 — Samples + Clinical Appendix",
                "Follow-up after sending ONCO-STAR full-text reprint. 20 minutes. Delivered 4 physician sample packs of OncoTarget (documented in sample log) plus printed subgroup analysis: exon 19 deletion median PFS 20.1 months vs L858R 17.4 months (HR 0.44 and 0.48 vs chemo, p<0.001 both). Provided rash management algorithm with dose-modification table. She agreed to try OncoTarget on two EGFR+ patients who refuse infusion center travel. Action: bring rash protocol laminated card to next visit. Sentiment: Cautiously positive.",
            ),
        ],
        "meeting": {
            "_id": "mtg_demo_chen_2026",
            "meeting_date": "2026-05-21T09:00:00Z",
            "objective": "Follow up on two EGFR+ sample patients — review tolerability, rash grading, and exon 19 subgroup outcomes; no marketing language",
            "pending": [
                "Confirm whether sample patients started OncoTarget",
                "Discuss Grade 2 rash management per protocol",
                "Offer grand rounds slot on ONCO-STAR mutation subgroups"
            ],
        },
    },
    "hcp_marcus_thorne": {
        "rep_id": "rep_rakesh_sharma",
        "primary_drug": "drug_cardioglyde",
        "tags": ["cardioglyde", "glp-1", "diabetes", "primary-care"],
        "visits": [
            (
                "2026-02-20",
                "Visit 1 — Corridor Introduction (CardioGlyde)",
                "5-minute corridor catch at Lilavati OPD — he was between patients (#38 of 40 for the day). Brief intro to CardioGlyde GLP-1 for T2DM with ASCVD. Neutral nod; said 'send me something I can read in two minutes.' Left one-page SURPASS-CARDIO MACE summary. Sentiment: Neutral, severely time-limited.",
            ),
            (
                "2026-04-05",
                "Visit 2 — Injection Objection",
                "Scheduled 10-minute slot; ran 7 minutes. Primary objection verbatim: 'My patients don't like injections — they want pills like MetaboMax.' He prescribes high volume of oral agents; injection pen seen as workflow friction for his nurses. Asked about patient assistance program and whether starter pens can be stored at clinic. Sentiment: Interested but blocked on route of administration.",
            ),
            (
                "2026-05-04",
                "Visit 3 — Samples + PAP + Pen Demo",
                "Delivered 6 CardioGlyde starter pens (sample log complete) plus pre-filled PAP enrollment forms for two uninsured patients. Showed 90-second once-weekly pen demo on tablet. He assigned two motivated obese T2DM patients for sample trial. Pending: follow up whether injections were tolerated. Sentiment: Positive/pragmatic.",
            ),
        ],
        "meeting": {
            "_id": "mtg_demo_thorne_2026",
            "meeting_date": "2026-05-23T11:30:00Z",
            "objective": "Punchy 10-minute follow-up: did the two sample patients tolerate weekly pen? Confirm PAP status and once-weekly dosing simplicity",
            "pending": [
                "Get feedback on GI tolerability for sample patients",
                "Leave tamil/english patient starter checklist (one page)",
                "Confirm PAP approval for uninsured patient"
            ],
        },
    },
    "hcp_emily_rodriguez": {
        "rep_id": "rep_priya_nair",
        "primary_drug": "drug_cardioglyde",
        "tags": ["cardioglyde", "metabomax", "endocrinology", "glp-1"],
        "visits": [
            (
                "2026-02-17",
                "Visit 1 — MetaboMax Loyalty Baseline",
                "15-minute meeting at Manipal endocrine clinic. She disclosed ~80% of her GLP-1 eligible patients are on competitor MetaboMax (oral semaglutide-class). Polite but firm: 'MetaboMax works for my practice.' Introduced CardioGlyde briefly; she asked for head-to-head data before any switch. Left formulary comparison sheet. Sentiment: Loyal to competitor.",
            ),
            (
                "2026-04-02",
                "Visit 2 — Oral Convenience Objection",
                "She doubled down: clinic nurses prefer MetaboMax because it is oral and needs no cold chain. Objection: 'Why would I choose an injection when MetaboMax is a pill?' Rep acknowledged convenience gap; promised SURPASS-CARDIO cardiovascular superiority data. She requested efficacy-over-convenience framing for physician-only discussion, not patient handouts. Sentiment: Skeptical.",
            ),
            (
                "2026-05-06",
                "Visit 3 — Efficacy vs MetaboMax Data Drop",
                "Delivered head-to-head positioning deck: CardioGlyde HbA1c -1.8% vs MetaboMax -1.2% at 40 weeks; weight loss 6.8 kg vs 3.1 kg; MACE reduction 26% (CardioGlyde) vs 11% (MetaboMax) in matched real-world cohort (internal medical affairs summary). She agreed to consider switching two MetaboMax non-responders as a trial. Samples: 4 CardioGlyde pens. Sentiment: Softening.",
            ),
        ],
        "meeting": {
            "_id": "mtg_demo_rodriguez_2026",
            "meeting_date": "2026-06-06T14:00:00Z",
            "objective": "Review outcomes for two MetaboMax-switch trial patients; reinforce efficacy-over-convenience and CV benefit vs MetaboMax",
            "pending": [
                "Bring MetaboMax vs CardioGlyde HbA1c/weight comparison one-pager",
                "Discuss nurse workflow: cold-chain pickup SOP",
                "Capture formulary committee timeline"
            ],
        },
    },
    "hcp_james_wilson": {
        "rep_id": "rep_arjun_desai",
        "primary_drug": "drug_cardioglyde",
        "tags": ["cardioglyde", "cardiology", "safety", "gi-tolerability"],
        "visits": [
            (
                "2026-02-19",
                "Visit 1 — Safety-First Introduction",
                "Max Hospital Delhi cardiology dept. 15 minutes. Introduced CardioGlyde for T2DM with established ASCVD. He was guarded — asked about pancreatitis case reports and GI discontinuation before any efficacy discussion. Neutral; said he rarely adopts new GLP-1s until safety database matures. Sentiment: Highly cautious.",
            ),
            (
                "2026-04-04",
                "Visit 2 — GI Side Effect Concern",
                "He cited three patients (colleagues' practices) who discontinued GLP-1 class due to nausea/vomiting. Specific objection: 'I will not expose my HFpEF diabetics to unpredictable GI toxicity.' Requested titration schedule and discontinuation rates from pivotal trials. Mentioned cold-chain storage as operational risk in Delhi summer. Sentiment: Skeptical.",
            ),
            (
                "2026-05-05",
                "Visit 3 — GI Titration Protocol + Safety Deck",
                "Provided GI tolerability titration protocol (4-week dose escalation), SURPASS-CARDIO GI AE table (nausea 18% vs 6% placebo; discontinuation 4.2% vs 1.1%), and cold-chain validated shipping SOP for Delhi clinics. He accepted written protocol for formulary review but has not prescribed. No samples yet — he requested safety first. Sentiment: Neutral-positive.",
            ),
        ],
        "meeting": {
            "_id": "mtg_demo_wilson_2026",
            "meeting_date": "2026-06-12T10:30:00Z",
            "objective": "Safety-focused follow-up: GI management in HFpEF+T2DM patients, eGFR monitoring plan, and pancreatitis signal context before first prescription",
            "pending": [
                "Bring pancreatitis epidemiology vs class background rates",
                "Provide eGFR-based dosing guardrails for CKD stage 3",
                "Discuss whether he is ready for limited sample use in low-risk patient"
            ],
        },
    },
    "hcp_michael_foster": {
        "rep_id": "rep_arjun_desai",
        "primary_drug": "drug_oncotarget",
        "tags": ["oncotarget", "venachemo", "oncology", "nsclc", "quality-of-life"],
        "visits": [
            (
                "2026-02-21",
                "Visit 1 — VenaChemo Baseline",
                "Fortis Gurgaon community oncology unit. 12 minutes. He is a high-volume VenaChemo (legacy IV EGFR chemo) prescriber — estimates 70% of EGFR+ lines start on VenaChemo. Introduced OncoTarget oral alternative. He said IV gives him 'visit visibility' for adherence. Neutral. Sentiment: Loyal to IV workflow.",
            ),
            (
                "2026-04-06",
                "Visit 2 — Adherence vs Infusion Monitoring",
                "Objection: with VenaChemo he knows patients received treatment because they sat in infusion chair; oral OncoTarget removes that visibility. Also raised VenaChemo toxicity as 'known devil' — neuropathy and fatigue predictable. Asked for quality-of-life comparison. Sentiment: Skeptical.",
            ),
            (
                "2026-05-07",
                "Visit 3 — QOL Data + First Oral Switch",
                "Shared ONCO-STAR patient-reported outcomes: 62% fewer infusion-related clinic hours; FACT-L score +8.4 points vs VenaChemo historical cohort. He agreed to switch one EGFR+ patient who refused further IV due to neuropathy. Provided 2 OncoTarget sample bottles + rash nursing hotline card. Sentiment: Cautiously open.",
            ),
        ],
        "meeting": {
            "_id": "mtg_demo_foster_2026",
            "meeting_date": "2026-06-19T15:00:00Z",
            "objective": "Follow up on first VenaChemo-to-OncoTarget switch — tolerability, rash, and quality-of-life vs infusion burden",
            "pending": [
                "Review week-4 tolerability for oral-switch patient",
                "Provide VenaChemo toxicity reminder vs OncoTarget AE profile",
                "Confirm infusion-chair capacity relief narrative for clinic manager"
            ],
        },
    },
}

COMPETITIVE_INTEL = [
    {
        "doc_id": "ci_metabomax_001",
        "competitor_drug": "MetaboMax",
        "therapeutic_area": "metabolics",
        "our_drug_ids": ["drug_cardioglyde"],
        "content": "MetaboMax (oral GLP-1 receptor agonist, competitor to CardioGlyde) is positioned on convenience: once-daily oral tablet, no injection, no pen training, and no cold-chain requirement in clinic. Real-world and pivotal summaries show HbA1c reduction approximately 1.0-1.2% at 40 weeks and mean weight loss ~3.1 kg — materially lower than CardioGlyde (-1.8% HbA1c, 6.8 kg weight loss in SURPASS-CARDIO). Cardiovascular outcome signal in matched cohorts is weaker (approx 11% MACE relative reduction vs 26% for CardioGlyde). Endocrinology KOLs who are MetaboMax-loyal (e.g., high oral adoption practices) respond to efficacy-over-convenience framing: (1) superior weight loss drives BP and lipid improvements, (2) proven CV benefit in established ASCVD, (3) once-weekly injection vs daily oral — adherence data favors weekly GLP-1 in Indian diabetes clinics when nurses support pen initiation. Counter MetaboMax objection 'patients want pills' by separating patient preference from clinical non-responder need — reserve oral competitor for injection-refusal only after documenting inadequate response.",
        "weakness_tags": [
            "lower-efficacy",
            "lower-weight-loss",
            "weaker-cv-outcomes",
            "daily-pill-burden",
            "no-superior-mace-data"
        ],
    },
    {
        "doc_id": "ci_venachemo_001",
        "competitor_drug": "VenaChemo",
        "therapeutic_area": "oncology",
        "our_drug_ids": ["drug_oncotarget"],
        "content": "VenaChemo is the legacy IV platinum-based regimen still used for EGFR-mutated NSCLC in community oncology settings with established infusion workflows. Strengths: decades of physician familiarity, infusion-center revenue, and perceived adherence monitoring because patients appear for chair time. Weaknesses: high toxicity — Grade 3+ neuropathy 22%, fatigue 41%, anemia 28%; median treatment-related hospitalization days 4.2 per cycle vs 0.6 for oral OncoTarget in ONCO-STAR safety tables. Progression-free survival inferior to OncoTarget (10.4 vs 18.9 months, HR 0.46, p<0.001). Counter-positioning for community oncologists loyal to VenaChemo: (1) oral OncoTarget eliminates infusion burden and chair capacity constraints, (2) superior PFS and ORR with manageable rash (8.2% Grade 3+), (3) patient quality-of-life scores significantly better — critical for palliative-minded prescribers, (4) home oral dosing with telemedicine check-ins replaces chair visibility without sacrificing safety monitoring.",
        "weakness_tags": [
            "high-toxicity",
            "inferior-pfs",
            "infusion-burden",
            "neuropathy-risk",
            "hospitalization-days"
        ],
    },
]

COMPANY_DOCS = [
    {
        "doc_id": "cd_cardioglyde_001",
        "doc_type": "datasheet",
        "drug_id": "drug_cardioglyde",
        "therapeutic_area": "metabolics",
        "title": "CardioGlyde (Glydepeptide) — GLP-1 Product Datasheet",
        "content": "CardioGlyde is a once-weekly subcutaneous GLP-1 receptor agonist for type 2 diabetes, weight management in adults with T2DM and obesity, and cardiovascular risk reduction in T2DM with established ASCVD. Storage: 2-8°C cold chain until first use; may be kept at room temperature up to 30°C for 28 days after first puncture. Key efficacy: HbA1c reduction 1.8% at 40 weeks; mean weight loss 6.8 kg at 52 weeks. Key safety: GI events manageable with 4-week titration (nausea 18%, discontinuation 4.2%). Differentiators vs oral MetaboMax: superior weight loss, stronger MACE reduction (26% in SURPASS-CARDIO), weekly vs daily dosing.",
        "tags": ["cardioglyde", "glp-1", "datasheet", "metabolics", "cardiology"],
    },
    {
        "doc_id": "cd_cardioglyde_002",
        "doc_type": "trial_summary",
        "drug_id": "drug_cardioglyde",
        "therapeutic_area": "metabolics",
        "title": "SURPASS-CARDIO — CardioGlyde Cardiovascular Outcomes Trial Summary",
        "content": "SURPASS-CARDIO randomized 9,840 adults with T2DM and established ASCVD to CardioGlyde vs standard of care. Primary endpoint MACE (CV death, non-fatal MI, non-fatal stroke): HR 0.74 (95% CI 0.61-0.89), p=0.002. Secondary: weight loss 6.8 kg vs 1.2 kg (p<0.001). GI management: dose escalation 0.25 mg x4 weeks then 0.5 mg; nausea peak week 4-6 then declines. Positioning vs MetaboMax: efficacy and CV outcomes trump oral convenience for non-responders and high-risk ASCVD patients.",
        "tags": ["cardioglyde", "surpass-cardio", "mace", "trial", "cardiology"],
    },
    {
        "doc_id": "cd_oncotarget_001",
        "doc_type": "datasheet",
        "drug_id": "drug_oncotarget",
        "therapeutic_area": "oncology",
        "title": "OncoTarget (Targotinib) — EGFR TKI Product Datasheet",
        "content": "OncoTarget is an oral once-daily EGFR tyrosine kinase inhibitor for locally advanced or metastatic NSCLC with EGFR exon 19 deletion or L858R mutation. Median PFS 18.9 months vs 10.4 months with platinum chemotherapy (HR 0.46, p<0.001). ORR 76% vs 31%. No infusion center required. Rash: Grade 3+ in 8.2%; dose modification per protocol. Differentiators vs VenaChemo IV: superior PFS, markedly lower Grade 3+ neuropathy and fatigue, improved patient-reported quality of life.",
        "tags": ["oncotarget", "egfr", "datasheet", "oncology", "nsclc"],
    },
    {
        "doc_id": "cd_oncotarget_002",
        "doc_type": "trial_summary",
        "drug_id": "drug_oncotarget",
        "therapeutic_area": "oncology",
        "title": "ONCO-STAR Phase III — OncoTarget vs Chemotherapy Full Statistical Summary",
        "content": "ONCO-STAR (n=512): OncoTarget vs platinum doublet in treatment-naive EGFR+ NSCLC. Primary endpoint PFS: 18.9 vs 10.4 months, HR 0.46 (95% CI 0.35-0.60), p<0.001. Subgroup exon 19 deletion: median PFS 20.1 months (HR 0.44, p<0.001); L858R: 17.4 months (HR 0.48, p<0.001). ORR 76% vs 31% (p<0.001). QOL: FACT-L +8.4 vs chemotherapy arm at week 24. For academic KOLs: emphasize mutation-subgroup hazard ratios; for community oncologists: emphasize toxicity and infusion-burden reduction vs VenaChemo.",
        "tags": ["oncotarget", "onco-star", "pfs", "egfr", "trial", "subgroup"],
    },
]


def load_json(name: str):
    path = DATA_DIR / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(name: str, data):
    path = DATA_DIR / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")


def strip_hcp_for_mongo(hcp: dict) -> dict:
    """Remove script-only fields not in Mongo schema."""
    return {k: v for k, v in hcp.items() if k not in ("territory_rep_id", "persona_type")}


def build_interaction_and_crm():
    interactions = []
    crm = []
    crm_id = 200
    for hcp_id, story in VISIT_STORIES.items():
        rep_id = story["rep_id"]
        drug_ids = [story["primary_drug"]]
        for i, (date, title, content) in enumerate(story["visits"], start=1):
            interactions.append(
                {
                    "doc_type": "interaction_note",
                    "hcp_id": hcp_id,
                    "rep_id": rep_id,
                    "tags": story["tags"],
                    "title": f"{title} — {hcp_id}",
                    "date": date,
                    "content": content,
                }
            )
            crm_id += 1
            crm.append(
                {
                    "doc_id": f"crm_{crm_id}",
                    "hcp_id": hcp_id,
                    "rep_id": rep_id,
                    "drug_ids": drug_ids,
                    "date": date,
                    "content": content,
                }
            )
    return interactions, crm


def build_meetings(hcps_by_id: dict):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    meetings = []
    locations = {
        "hcp_sarah_chen": "Tata Memorial Centre, Mumbai — Thoracic Oncology Conference Room A",
        "hcp_marcus_thorne": "Lilavati Hospital, Mumbai — OPD Block 2, Room 118",
        "hcp_emily_rodriguez": "Manipal Hospital Bangalore — Endocrinology Suite, 3rd Floor",
        "hcp_james_wilson": "Max Super Speciality Hospital, New Delhi — Cardiology Wing",
        "hcp_michael_foster": "Fortis Memorial Research Institute, Gurgaon — Oncology Day Care",
    }
    samples_map = {
        "hcp_sarah_chen": [{"drug_id": "drug_oncotarget", "quantity": 2}],
        "hcp_marcus_thorne": [{"drug_id": "drug_cardioglyde", "quantity": 4}],
        "hcp_emily_rodriguez": [{"drug_id": "drug_cardioglyde", "quantity": 4}],
        "hcp_james_wilson": [],
        "hcp_michael_foster": [{"drug_id": "drug_oncotarget", "quantity": 2}],
    }
    for hcp_id, story in VISIT_STORIES.items():
        m = story["meeting"]
        primary = story["primary_drug"]
        hcp = hcps_by_id[hcp_id]
        meetings.append(
            {
                "_id": m["_id"],
                "rep_id": story["rep_id"],
                "hcp_id": hcp_id,
                "drug_ids": [primary],
                "detailing_sequence": [primary],
                "objective": m["objective"],
                "planned_samples": samples_map[hcp_id],
                "pending_action_items": m["pending"],
                "meeting_date": m["meeting_date"],
                "location": locations[hcp_id],
                "duration_mins": 20 if "thorne" in hcp_id else 25,
                "status": "scheduled",
                "agent_triggered": False,
                "briefing_id": None,
                "created_at": now,
            }
        )
    # Additional June meetings for portfolio coverage
    extra = [
        {
            "_id": "mtg_demo_portfolio_may_2026",
            "rep_id": "rep_rakesh_sharma",
            "hcp_id": "hcp_sarah_chen",
            "drug_ids": ["drug_oncotarget", "drug_cardioglyde"],
            "detailing_sequence": ["drug_oncotarget"],
            "objective": "Quarterly portfolio touchpoint — OncoTarget pipeline update only (no CardioGlyde detail per HCP request)",
            "planned_samples": [],
            "pending_action_items": ["Confirm CME slot for ONCO-STAR subgroup presentation"],
            "meeting_date": "2026-06-25T10:00:00Z",
            "location": "Tata Memorial Centre, Mumbai — Research Admin Building",
            "duration_mins": 15,
            "status": "scheduled",
            "agent_triggered": False,
            "briefing_id": None,
            "created_at": now,
        },
        {
            "_id": "mtg_demo_cardio_june_2026",
            "rep_id": "rep_priya_nair",
            "hcp_id": "hcp_emily_rodriguez",
            "drug_ids": ["drug_cardioglyde"],
            "detailing_sequence": ["drug_cardioglyde"],
            "objective": "Mid-year MetaboMax competitive review — formulary discussion prep",
            "planned_samples": [{"drug_id": "drug_cardioglyde", "quantity": 2}],
            "pending_action_items": [
                "Bring nurse cold-chain workflow one-pager",
                "Document MetaboMax non-responder case series"
            ],
            "meeting_date": "2026-06-28T11:00:00Z",
            "location": "Manipal Hospital Bangalore — Pharmacy & Therapeutics Prep Meeting",
            "duration_mins": 30,
            "status": "scheduled",
            "agent_triggered": False,
            "briefing_id": None,
            "created_at": now,
        },
    ]
    meetings.extend(extra)
    return meetings


def shift_legacy_meetings_to_2026(meetings: list) -> list:
    """Move 2025 meeting_date strings to 2026 for demo recency."""
    for m in meetings:
        if "2025" in m.get("meeting_date", ""):
            m["meeting_date"] = m["meeting_date"].replace("2025", "2026")
    return meetings


def merge_unique(existing: list, new_items: list, key: str) -> list:
    seen = {item[key] for item in existing if key in item}
    for item in new_items:
        if item[key] not in seen:
            existing.append(item)
            seen.add(item[key])
    return existing


def main():
    # HCPs
    hcps = load_json("hcp_profiles.json")
    existing_ids = {h["_id"] for h in hcps}
    for hcp in NEW_HCPS:
        if hcp["_id"] not in existing_ids:
            hcps.append(strip_hcp_for_mongo(hcp))
    save_json("hcp_profiles.json", hcps)

    hcps_by_id = {h["_id"]: h for h in NEW_HCPS}

    # Interaction notes & CRM
    new_interactions, new_crm = build_interaction_and_crm()
    interactions = load_json("interaction_notes.json")
    crm = load_json("elastic_crm_memory.json")
    interactions.extend(new_interactions)
    crm.extend(new_crm)
    save_json("interaction_notes.json", interactions)
    save_json("elastic_crm_memory.json", crm)

    # Competitive intel & company docs
    ci = load_json("elastic_competitive_intel.json")
    ci = merge_unique(ci, COMPETITIVE_INTEL, "doc_id")
    save_json("elastic_competitive_intel.json", ci)

    docs = load_json("elastic_company_docs.json")
    docs = merge_unique(docs, COMPANY_DOCS, "doc_id")
    save_json("elastic_company_docs.json", docs)

    # Meetings
    meetings = load_json("meetings.json")
    meetings = shift_legacy_meetings_to_2026(meetings)
    new_meetings = build_meetings(hcps_by_id)
    meetings = merge_unique(meetings, new_meetings, "_id")
    save_json("meetings.json", meetings)

    print("Pharma demo data generation complete.")
    print(f"  HCPs: {len(hcps)} total ({len(NEW_HCPS)} new personas)")
    print(f"  Interaction notes: +{len(new_interactions)}")
    print(f"  CRM memory docs: +{len(new_crm)}")
    print(f"  Competitive intel: +{len(COMPETITIVE_INTEL)}")
    print(f"  Company docs: +{len(COMPANY_DOCS)}")
    print(f"  Meetings: +{len(new_meetings)} (May–June 2026)")


if __name__ == "__main__":
    main()
