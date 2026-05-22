"""
pubmed_tools.py — PubMed & ClinicalTrials.gov Search Tool Functions
====================================================================
Pure Python functions that query external biomedical literature APIs.
Each function is registered as a tool for the ADK agent (Gemini).

Google ADK uses the docstrings to understand what each tool does,
what arguments it takes, and what it returns — so docstrings here
are critical and must be precise.

APIs used:
  - NCBI E-utilities (esearch + efetch) for PubMed abstracts
  - ClinicalTrials.gov v2 REST API for completed study metadata

No API keys are required for low-volume usage (<3 req/s for NCBI).
All network errors are caught and returned as structured dicts —
these functions never raise exceptions to the caller.
"""

import requests
import xml.etree.ElementTree as ET


# ── NCBI E-utilities base URLs ────────────────────────────────
_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# ── ClinicalTrials.gov v2 base URL ───────────────────────────
_CT_STUDIES_URL = "https://clinicaltrials.gov/api/v2/studies"


def search_pubmed(query: str, max_results: str) -> dict:
    """Searches PubMed for biomedical literature matching a query
    and returns titles, abstract snippets, and publication dates.

    This function performs a two-step process using NCBI E-utilities:
      1. esearch — find PubMed IDs (PMIDs) matching the query.
      2. efetch  — retrieve article metadata (title, abstract, date)
         for the top results.

    The agent should call this when it needs published clinical
    evidence, peer-reviewed data, or recent literature references
    to strengthen talking points in a briefing.

    Args:
        query: Natural language or MeSH-based search query for
            PubMed (e.g. "ACE inhibitor hypertension renal
            protection" or "lisinopril diabetic nephropathy").
        max_results: Maximum number of articles to return, as a
            string (e.g. "5"). Will be clamped to 1–20 internally.

    Returns:
        A dict with the following structure:
        {
            "status": "success",
            "total_found": 1542,
            "results": [
                {
                    "pmid": "38291045",
                    "title": "Renal protective effects of ...",
                    "abstract_snippet": "Background: ACE inhibitors ...",
                    "pub_date": "2024 Jan"
                },
                ...
            ]
        }
        On error returns:
        {
            "status": "error",
            "message": "...",
            "results": []
        }
    """
    # ── Parse and clamp max_results ────────────────────────────
    try:
        n = int(max_results)
        n = max(1, min(n, 20))
    except (ValueError, TypeError):
        n = 5

    # ── Step 1: esearch — get PMIDs ───────────────────────────
    try:
        esearch_resp = requests.get(
            _ESEARCH_URL,
            params={
                "db": "pubmed",
                "term": query,
                "retmax": n,
                "retmode": "json",
                "sort": "relevance",
            },
            timeout=15,
        )
        esearch_resp.raise_for_status()
        esearch_data = esearch_resp.json()
    except requests.RequestException as exc:
        return {
            "status": "error",
            "message": f"PubMed esearch failed: {exc}",
            "results": [],
        }

    id_list = esearch_data.get("esearchresult", {}).get("idlist", [])
    total_found = int(
        esearch_data.get("esearchresult", {}).get("count", 0)
    )

    if not id_list:
        return {
            "status": "success",
            "total_found": total_found,
            "results": [],
        }

    # ── Step 2: efetch — retrieve article metadata (XML) ──────
    try:
        efetch_resp = requests.get(
            _EFETCH_URL,
            params={
                "db": "pubmed",
                "id": ",".join(id_list),
                "rettype": "xml",
                "retmode": "xml",
            },
            timeout=15,
        )
        efetch_resp.raise_for_status()
    except requests.RequestException as exc:
        return {
            "status": "error",
            "message": f"PubMed efetch failed: {exc}",
            "results": [],
        }

    # ── Parse XML response ────────────────────────────────────
    results = []
    try:
        root = ET.fromstring(efetch_resp.content)
        for article_el in root.findall(".//PubmedArticle"):
            # — PMID
            pmid_el = article_el.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""

            # — Title
            title_el = article_el.find(".//ArticleTitle")
            title = title_el.text if title_el is not None else ""

            # — Abstract (concatenate all AbstractText elements)
            abstract_parts = []
            for abs_el in article_el.findall(".//AbstractText"):
                label = abs_el.get("Label", "")
                # itertext() captures mixed-content (tags inside text)
                text = "".join(abs_el.itertext()).strip()
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            full_abstract = " ".join(abstract_parts)
            # Truncate to a readable snippet (first 500 chars)
            snippet = full_abstract[:500] + ("..." if len(full_abstract) > 500 else "")

            # — Publication date (prefer MedlineDate, then Year+Month)
            pub_date = ""
            pubdate_el = article_el.find(".//PubDate")
            if pubdate_el is not None:
                medline_date = pubdate_el.findtext("MedlineDate")
                if medline_date:
                    pub_date = medline_date
                else:
                    year = pubdate_el.findtext("Year", "")
                    month = pubdate_el.findtext("Month", "")
                    pub_date = f"{year} {month}".strip()

            results.append({
                "pmid": pmid,
                "title": title,
                "abstract_snippet": snippet,
                "pub_date": pub_date,
            })
    except ET.ParseError as exc:
        return {
            "status": "error",
            "message": f"PubMed XML parse failed: {exc}",
            "results": [],
        }

    return {
        "status": "success",
        "total_found": total_found,
        "results": results,
    }


def search_clinical_trials(query: str, max_results: str) -> dict:
    """Searches ClinicalTrials.gov for completed clinical studies
    matching a query and returns trial metadata.

    Uses the ClinicalTrials.gov v2 REST API with a filter for
    COMPLETED studies only. Returns key trial identifiers including
    NCT ID, title, phase, and enrollment count.

    The agent should call this when it needs real-world trial
    evidence, study phase data, or enrollment numbers to support
    clinical claims in a briefing.

    Args:
        query: Natural language search query describing the
            clinical area or drug of interest (e.g. "ACE inhibitor
            hypertension" or "lisinopril renal protection").
        max_results: Maximum number of studies to return, as a
            string (e.g. "5"). Will be clamped to 1–20 internally.

    Returns:
        A dict with the following structure:
        {
            "status": "success",
            "total_found": 312,
            "results": [
                {
                    "nctId": "NCT01234567",
                    "briefTitle": "Lisinopril vs Placebo in ...",
                    "phase": "PHASE3",
                    "enrollment": 1200
                },
                ...
            ]
        }
        On error returns:
        {
            "status": "error",
            "message": "...",
            "results": []
        }
    """
    # ── Parse and clamp max_results ────────────────────────────
    try:
        n = int(max_results)
        n = max(1, min(n, 20))
    except (ValueError, TypeError):
        n = 5

    # ── Call ClinicalTrials.gov v2 API ────────────────────────
    try:
        resp = requests.get(
            _CT_STUDIES_URL,
            params={
                "query.term": query,
                "filter.overallStatus": "COMPLETED",
                "pageSize": n,
                "format": "json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        return {
            "status": "error",
            "message": f"ClinicalTrials.gov API failed: {exc}",
            "results": [],
        }
    except ValueError as exc:
        return {
            "status": "error",
            "message": f"ClinicalTrials.gov JSON decode failed: {exc}",
            "results": [],
        }

    # ── Parse studies from response ───────────────────────────
    studies = data.get("studies", [])
    results = []
    for study in studies:
        protocol = study.get("protocolSection", {})
        id_module = protocol.get("identificationModule", {})
        design_module = protocol.get("designModule", {})

        nct_id = id_module.get("nctId", "")
        brief_title = id_module.get("briefTitle", "")

        # Phase may be a list e.g. ["PHASE3"] — join if multiple
        phases = design_module.get("phases", [])
        phase = ", ".join(phases) if phases else "N/A"

        # Enrollment info
        enrollment_info = design_module.get("enrollmentInfo", {})
        enrollment = enrollment_info.get("count", 0)

        results.append({
            "nctId": nct_id,
            "briefTitle": brief_title,
            "phase": phase,
            "enrollment": enrollment,
        })

    # ── Determine total count ─────────────────────────────────
    # The v2 API returns totalCount at the top level when available
    total_found = data.get("totalCount", len(results))

    return {
        "status": "success",
        "total_found": total_found,
        "results": results,
    }


# ═══════════════════════════════════════════════════════════════
# Test block — run: python tools/pubmed_tools.py
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  pubmed_tools.py — Test Run")
    print("=" * 60)

    test_query = "ACE inhibitor hypertension"

    # ── Test 1: search_pubmed ──────────────────────────────────
    print(f"\n🔍 Test 1: search_pubmed('{test_query}', '3')")
    print("-" * 50)
    result1 = search_pubmed(test_query, "3")
    print(f"   Status: {result1['status']}")
    if result1["status"] == "success":
        print(f"   Total found: {result1['total_found']}")
        print(f"   Returned: {len(result1['results'])}")
        for r in result1["results"]:
            print(f"\n   📄 PMID {r['pmid']} ({r['pub_date']})")
            print(f"      Title: {r['title']}")
            snippet = r["abstract_snippet"][:120]
            print(f"      Abstract: {snippet}...")
    else:
        print(f"   Error: {result1.get('message', 'unknown')}")
    print()

    # ── Test 2: search_clinical_trials ─────────────────────────
    print(f"🔍 Test 2: search_clinical_trials('{test_query}', '3')")
    print("-" * 50)
    result2 = search_clinical_trials(test_query, "3")
    print(f"   Status: {result2['status']}")
    if result2["status"] == "success":
        print(f"   Total found: {result2['total_found']}")
        print(f"   Returned: {len(result2['results'])}")
        for r in result2["results"]:
            print(f"\n   🧪 {r['nctId']} — Phase: {r['phase']}")
            print(f"      Title: {r['briefTitle'][:100]}")
            print(f"      Enrollment: {r['enrollment']}")
    else:
        print(f"   Error: {result2.get('message', 'unknown')}")

    print("\n✅ All tests complete.\n")
