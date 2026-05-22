"""Smoke tests for MVP+ multi-drug meeting schema support."""

from tools import mongo_tools
from agent.compliance_agent import COMPLIANCE_INSTRUCTION
from agent.planner_agent import PLANNER_INSTRUCTION
from agent.retriever_agent import RETRIEVER_INSTRUCTION
from agent.writer_agent import WRITER_INSTRUCTION


class FakeCursor(list):
    pass


class FakeCollection:
    def __init__(self, documents):
        self.documents = {document["_id"]: document for document in documents}

    def find_one(self, query):
        return self.documents.get(query["_id"])

    def find(self, query):
        ids = query.get("_id", {}).get("$in", [])
        return FakeCursor(
            [self.documents[item_id] for item_id in ids if item_id in self.documents]
        )


class FakeDB:
    def __init__(self):
        self.collections = {
            "meetings": FakeCollection(
                [
                    {
                        "_id": "legacy_meeting",
                        "rep_id": "rep_1",
                        "hcp_id": "hcp_1",
                        "drug_id": "drug_a",
                    },
                    {
                        "_id": "multi_meeting",
                        "rep_id": "rep_1",
                        "hcp_id": "hcp_1",
                        "drug_ids": ["drug_a", "drug_b"],
                        "detailing_sequence": ["drug_b", "drug_a"],
                        "objective": "Position portfolio",
                        "planned_samples": [{"drug_id": "drug_a", "quantity": 10}],
                        "pending_action_items": ["Send safety data"],
                    },
                ]
            ),
            "sales_reps": FakeCollection([{"_id": "rep_1", "name": "Rep One"}]),
            "hcp_profiles": FakeCollection([{"_id": "hcp_1", "name": "Dr. One"}]),
            "drugs": FakeCollection(
                [
                    {"_id": "drug_a", "brand_name": "Drug A"},
                    {"_id": "drug_b", "brand_name": "Drug B"},
                ]
            ),
        }

    def __getitem__(self, collection_name):
        return self.collections[collection_name]


def test_get_meeting_supports_legacy_drug_id():
    original_db = mongo_tools._db
    mongo_tools._db = FakeDB()
    try:
        result = mongo_tools.get_meeting("legacy_meeting")
    finally:
        mongo_tools._db = original_db

    assert result["status"] == "found"
    assert result["drug_ids"] == ["drug_a"]
    assert [drug["_id"] for drug in result["drugs"]] == ["drug_a"]
    assert result["drug"]["_id"] == "drug_a"


def test_get_meeting_supports_multi_drug_sequence():
    original_db = mongo_tools._db
    mongo_tools._db = FakeDB()
    try:
        result = mongo_tools.get_meeting("multi_meeting")
    finally:
        mongo_tools._db = original_db

    assert result["status"] == "found"
    assert result["drug_ids"] == ["drug_b", "drug_a"]
    assert [drug["_id"] for drug in result["drugs"]] == ["drug_b", "drug_a"]
    assert result["meeting"]["objective"] == "Position portfolio"
    assert result["meeting"]["planned_samples"][0]["quantity"] == 10
    assert result["meeting"]["pending_action_items"] == ["Send safety data"]


def test_agent_instructions_include_mvp_plus_fields():
    required_terms = [
        "objective",
        "planned_samples",
        "pending_action_items",
        "detailing_sequence",
    ]

    for term in required_terms:
        assert term in PLANNER_INSTRUCTION
        assert term in RETRIEVER_INSTRUCTION

    assert "rep_workflow_notes" in WRITER_INSTRUCTION
    assert "evidence_ledger" in WRITER_INSTRUCTION
    assert "Physician Sample - Not for Sale" in WRITER_INSTRUCTION
    assert "sample reminder" in COMPLIANCE_INSTRUCTION.lower()
    assert "quality_gate_result" in COMPLIANCE_INSTRUCTION
    assert "Physician Sample - Not for Sale" in COMPLIANCE_INSTRUCTION


if __name__ == "__main__":
    test_get_meeting_supports_legacy_drug_id()
    test_get_meeting_supports_multi_drug_sequence()
    test_agent_instructions_include_mvp_plus_fields()
    print("MVP+ schema smoke tests passed.")
