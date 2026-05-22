"""Tests for deterministic evidence grounding and claim quality checks."""

from tools.evidence_grounding import build_evidence_ledger, validate_claim_quality


CARDIOGLYDE_RETRIEVED_CONTEXT = {
    "status": "retrieved",
    "per_drug": {
        "drug_cardioglyde": {
            "drug_id": "drug_cardioglyde",
            "drug_name": "CardioGlyde",
            "generic_name": "Glydepeptide",
            "drug_class": "GLP-1 Receptor Agonist",
            "therapeutic_area": "cardiology",
            "company_docs": {
                "results": [
                    {
                        "doc_id": "cd_008",
                        "title": "SURPASS-CARDIO — CardioGlyde Cardiovascular Outcomes Trial Summary",
                        "content": (
                            "SURPASS-CARDIO randomized 9,840 adults with T2DM and established ASCVD "
                            "to CardioGlyde vs standard of care. Primary endpoint MACE: HR 0.74 "
                            "(95% CI 0.61-0.89), p=0.002. Secondary: weight loss 6.8 kg vs 1.2 kg "
                            "(p<0.001). HbA1c reduction 1.8% at 40 weeks."
                        ),
                    }
                ]
            },
            "competitive_intel": {"results": []},
            "pubmed": {
                "results": [
                    {
                        "pmid": "33181201",
                        "title": "Does background metformin therapy influence the cardiovascular outcomes with SGLT-2 inhibitors in type 2 diabetes?",
                        "abstract_snippet": "N = 7,233; HR 0.79; 95% CI, 0.69-0.90; p < 0.01.",
                    }
                ]
            },
            "clinical_trials": {"results": []},
        }
    },
}


def test_pubmed_background_metformin_is_not_cardioglyde_support():
    ledger = build_evidence_ledger(CARDIOGLYDE_RETRIEVED_CONTEXT)
    pubmed_entry = next(entry for entry in ledger if entry["source_id"] == "33181201")

    assert pubmed_entry["drug_id"] == "drug_cardioglyde"
    assert pubmed_entry["source_scope"] == "background_therapy"
    assert pubmed_entry["claim_role"] == "background_therapy"


def test_vague_talking_point_without_numbers_is_rejected():
    draft = {
        "status": "drafted",
        "meeting_id": "mtg_rakesh_001",
        "hcp_id": "hcp_ananya_mehta",
        "rep_id": "rep_rakesh_sharma",
        "drug_sections": [
            {
                "drug_id": "drug_cardioglyde",
                "drug_name": "CardioGlyde",
                "key_talking_points": [
                    {
                        "point": "Significant weight loss benefits observed at 52 weeks.",
                        "source": {"type": "InternalDoc", "doc_id": "cd_008", "title": "SURPASS-CARDIO"},
                        "specific_numbers": [],
                    }
                ],
            }
        ],
    }

    result = validate_claim_quality(draft, CARDIOGLYDE_RETRIEVED_CONTEXT)

    assert result["passed"] is False
    assert any(flag["rule_id"] == "claim_quality_numbers" for flag in result["flags"])


def test_cardioglyde_numeric_internaldoc_claim_passes_and_populates_evidence():
    draft = {
        "status": "drafted",
        "meeting_id": "mtg_rakesh_001",
        "hcp_id": "hcp_ananya_mehta",
        "rep_id": "rep_rakesh_sharma",
        "drug_sections": [
            {
                "drug_id": "drug_cardioglyde",
                "drug_name": "CardioGlyde",
                "key_talking_points": [
                    {
                        "point": (
                            "For T2DM with established ASCVD, SURPASS-CARDIO reported MACE HR 0.74 "
                            "(95% CI 0.61-0.89; p=0.002) for CardioGlyde vs standard of care."
                        ),
                        "source": {"type": "InternalDoc", "doc_id": "cd_008", "title": "SURPASS-CARDIO"},
                        "specific_numbers": ["HR 0.74", "95% CI 0.61-0.89", "p=0.002"],
                    },
                    {
                        "point": (
                            "For weight discussion, SURPASS-CARDIO reported mean weight loss of 6.8 kg "
                            "vs 1.2 kg at 52 weeks (p<0.001)."
                        ),
                        "source": {"type": "InternalDoc", "doc_id": "cd_008", "title": "SURPASS-CARDIO"},
                        "specific_numbers": ["6.8 kg", "1.2 kg", "52 weeks", "p<0.001"],
                    },
                    {
                        "point": "For glycaemic control, CardioGlyde reduced HbA1c by 1.8% at 40 weeks as add-on therapy.",
                        "source": {"type": "InternalDoc", "doc_id": "cd_008", "title": "SURPASS-CARDIO"},
                        "specific_numbers": ["1.8%", "40 weeks"],
                    },
                ],
            }
        ],
    }

    result = validate_claim_quality(draft, CARDIOGLYDE_RETRIEVED_CONTEXT)

    assert result["passed"] is True
    clean_brief = result["clean_brief"]
    assert clean_brief["quality_gate_status"] == "passed"
    assert clean_brief["supporting_evidence"][0]["doc_id"] == "cd_008"
    assert "6.8 kg" in clean_brief["drug_sections"][0]["key_talking_points"][1]["point"]
    assert "1.8%" in clean_brief["drug_sections"][0]["key_talking_points"][2]["point"]


def test_background_pubmed_claim_for_featured_drug_is_rejected():
    draft = {
        "status": "drafted",
        "meeting_id": "mtg_rakesh_001",
        "hcp_id": "hcp_ananya_mehta",
        "rep_id": "rep_rakesh_sharma",
        "drug_sections": [
            {
                "drug_id": "drug_cardioglyde",
                "drug_name": "CardioGlyde",
                "key_talking_points": [
                    {
                        "point": "CardioGlyde showed MACE HR 0.79 in high-risk T2DM patients.",
                        "source": {"type": "PubMed", "pmid": "33181201", "title": "Background metformin therapy"},
                        "specific_numbers": ["HR 0.79"],
                    }
                ],
            }
        ],
    }

    result = validate_claim_quality(draft, CARDIOGLYDE_RETRIEVED_CONTEXT)

    assert result["passed"] is False
    assert any(flag["rule_id"] == "claim_quality_source_scope" for flag in result["flags"])


if __name__ == "__main__":
    test_pubmed_background_metformin_is_not_cardioglyde_support()
    test_vague_talking_point_without_numbers_is_rejected()
    test_cardioglyde_numeric_internaldoc_claim_passes_and_populates_evidence()
    test_background_pubmed_claim_for_featured_drug_is_rejected()
    print("Evidence grounding tests passed.")
