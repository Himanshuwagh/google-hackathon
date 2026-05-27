"""Tests for MongoDB-backed retrieval tools."""

from tools import mongo_retrieval_tools as tools
from db import seed_mongodb_retrieval


class FakeCursor:
    def __init__(self, documents):
        self.documents = list(documents)

    def sort(self, field, direction):
        reverse = direction < 0
        self.documents.sort(key=lambda item: item.get(field, ""), reverse=reverse)
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    def __iter__(self):
        return iter(self.documents)


class FakeCollection:
    def __init__(self, documents):
        self.documents = list(documents)

    def aggregate(self, pipeline):
        del pipeline
        raise RuntimeError("Atlas Search unavailable in unit test")

    def find(self, query, projection=None):
        del projection
        matched = []
        for document in self.documents:
            if _matches(document, query):
                matched.append(dict(document))
        return FakeCursor(matched)


class FakeWritableCollection(FakeCollection):
    def delete_many(self, query):
        del query
        self.documents = []

    def insert_many(self, documents):
        self.documents.extend(dict(document) for document in documents)

    def count_documents(self, query):
        del query
        return len(self.documents)


def _matches(document, query):
    for key, expected in query.items():
        value = document.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if value not in expected["$in"]:
                return False
        elif value != expected:
            return False
    return True


def _patch_collections(collections):
    original_collection = tools._collection
    original_embed_text = tools.embed_text
    tools._collection = lambda name: FakeCollection(collections[name])
    tools.embed_text = lambda text: []
    return original_collection, original_embed_text


def _restore(originals):
    tools._collection, tools.embed_text = originals


def test_company_doc_search_respects_drug_id_and_shape():
    originals = _patch_collections(
        {
            "company_docs": [
                {
                    "doc_id": "cd_1",
                    "drug_id": "drug_a",
                    "title": "Renal outcomes",
                    "description": "Trial",
                    "source": "Journal",
                    "pdf_url": "https://example.test",
                    "content": "renal protection diabetic albuminuria",
                    "doc_type": "clinical_trial",
                    "tags": ["renal"],
                },
                {
                    "doc_id": "cd_2",
                    "drug_id": "drug_b",
                    "title": "Wrong drug",
                    "content": "renal protection diabetic",
                },
            ]
        }
    )
    try:
        result = tools.search_company_docs("renal diabetic", "drug_a")
    finally:
        _restore(originals)

    assert result["status"] == "success"
    assert result["retrieval_backend"] == "mongodb_atlas_hybrid"
    assert result["total_hits"] == 1
    assert result["results"][0]["doc_id"] == "cd_1"
    assert result["results"][0]["title"] == "Renal outcomes"
    assert result["results"][0]["doc_type"] == "clinical_trial"


def test_crm_memory_filters_hcp_and_sorts_recent_first():
    originals = _patch_collections(
        {
            "crm_memory": [
                {"doc_id": "old", "hcp_id": "hcp_1", "date": "2025-01-01", "content": "old"},
                {"doc_id": "new", "hcp_id": "hcp_1", "date": "2025-03-01", "content": "new"},
                {"doc_id": "other", "hcp_id": "hcp_2", "date": "2025-04-01", "content": "other"},
            ]
        }
    )
    try:
        result = tools.search_crm_memory("hcp_1")
    finally:
        _restore(originals)

    assert [item["doc_id"] for item in result["results"]] == ["new", "old"]
    assert all(item["hcp_id"] == "hcp_1" for item in result["results"])


def test_competitive_intel_respects_therapeutic_area_and_shape():
    originals = _patch_collections(
        {
            "competitive_intel": [
                {
                    "doc_id": "ci_1",
                    "competitor_drug": "Competitor A",
                    "therapeutic_area": "cardiology",
                    "our_drug_ids": ["drug_a"],
                    "content": "price objection market support",
                    "weakness_tags": ["price-only"],
                },
                {
                    "doc_id": "ci_2",
                    "competitor_drug": "Competitor B",
                    "therapeutic_area": "oncology",
                    "content": "price objection market support",
                },
            ]
        }
    )
    try:
        result = tools.search_competitive_intel("price market", "cardiology")
    finally:
        _restore(originals)

    assert result["total_hits"] == 1
    assert result["results"][0]["doc_id"] == "ci_1"
    assert result["results"][0]["weakness_tags"] == ["price-only"]


def test_rrf_merge_combines_vector_and_text_rankings():
    merged = tools._rrf_merge(
        [{"doc_id": "a"}, {"doc_id": "b"}],
        [{"doc_id": "b"}, {"doc_id": "c"}],
        limit=3,
    )

    assert [item["doc_id"] for item in merged] == ["b", "a", "c"]
    assert merged[0]["_matched_by"] == ["vector", "text"]


def test_seed_collection_preserves_source_fields_without_embedding():
    collection = FakeWritableCollection([{"doc_id": "old"}])
    count = seed_mongodb_retrieval._seed_collection(
        collection,
        [
            {
                "doc_id": "crm_1",
                "hcp_id": "hcp_1",
                "rep_id": "rep_1",
                "drug_ids": ["drug_a"],
                "date": "2025-01-01",
                "content": "source note",
            }
        ],
        kind="crm_memory",
        embed=False,
    )

    assert count == 1
    assert collection.documents[0]["_id"] == "crm_1"
    assert collection.documents[0]["content"] == "source note"
    assert collection.documents[0]["corpus_kind"] == "crm_memory"


if __name__ == "__main__":
    test_company_doc_search_respects_drug_id_and_shape()
    test_crm_memory_filters_hcp_and_sorts_recent_first()
    test_competitive_intel_respects_therapeutic_area_and_shape()
    test_rrf_merge_combines_vector_and_text_rankings()
    test_seed_collection_preserves_source_fields_without_embedding()
    print("MongoDB retrieval tests passed.")
