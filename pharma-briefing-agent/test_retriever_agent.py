"""Simple smoke test for the InformationRetriever ADK agent."""

import asyncio

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent.retriever_agent import retriever_agent


APP_NAME = "pharma_briefing_agent"
USER_ID = "test_user"
SESSION_ID = "test_retriever_session"


SAMPLE_EXECUTION_PLAN = {
    "status": "planned",
    "meeting_id": "mtg_demo_multi_001",
    "hcp_id": "hcp_ananya_mehta",
    "objective": "Address cost concerns and position hypertension portfolio for mixed cardiac patients",
    "planned_samples": [{"drug_id": "drug_lisinopril_10mg", "quantity": 10}],
    "pending_action_items": [
        "Provide renal safety data for diabetic hypertensive patients",
        "Clarify patient assistance program eligibility",
    ],
    "detailing_sequence": ["drug_lisinopril_10mg", "drug_amlodipine_5mg"],
    "meeting_context": {
        "hcp": {
            "hcp_id": "hcp_ananya_mehta",
            "name": "Dr. Ananya Mehta",
            "specialty": "Cardiology",
            "known_objections": [
                "prefers generic brands",
                "cost-sensitive patients",
            ],
        },
        "objective": "Address cost concerns and position hypertension portfolio for mixed cardiac patients",
        "planned_samples": [{"drug_id": "drug_lisinopril_10mg", "quantity": 10}],
        "pending_action_items": [
            "Provide renal safety data for diabetic hypertensive patients",
            "Clarify patient assistance program eligibility",
        ],
    },
    "drug_ids": ["drug_lisinopril_10mg", "drug_amlodipine_5mg"],
    "drugs": [
        {
            "drug_id": "drug_lisinopril_10mg",
            "drug_name": "Lisinopril 10mg",
            "generic_name": "Lisinopril",
            "drug_class": "ACE Inhibitor",
            "therapeutic_area": "cardiology",
            "company_doc_query": "Lisinopril 10mg hypertension heart failure approved claims patient assistance India",
            "competitive_query": "generic lisinopril ACE inhibitor cost comparison India cardiology",
            "pubmed_query": "lisinopril hypertension heart failure outcomes India",
            "clinical_trials_query": "lisinopril hypertension heart failure outcomes India",
        },
        {
            "drug_id": "drug_amlodipine_5mg",
            "drug_name": "Amlodipine 5mg",
            "generic_name": "Amlodipine Besylate",
            "drug_class": "Calcium Channel Blocker (Dihydropyridine)",
            "therapeutic_area": "cardiology",
            "company_doc_query": "Amlodipine 5mg hypertension approved claims 24h BP control India",
            "competitive_query": "amlodipine calcium channel blocker hypertension price comparison India",
            "pubmed_query": "amlodipine hypertension efficacy cardiovascular outcomes India",
            "clinical_trials_query": "amlodipine hypertension efficacy cardiovascular outcomes India",
        },
    ],
}


async def main() -> None:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        state={"execution_plan": SAMPLE_EXECUTION_PLAN},
    )

    runner = Runner(
        app_name=APP_NAME,
        agent=retriever_agent,
        session_service=session_service,
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text="Run retrieval for the execution_plan in state.")],
    )

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=message,
    ):
        if not event.is_final_response() or not event.content:
            continue

        for part in event.content.parts or []:
            if part.text:
                print(part.text)


if __name__ == "__main__":
    asyncio.run(main())
