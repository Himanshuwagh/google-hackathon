"""Simple smoke test for the MeetingPlanner ADK agent."""

import asyncio

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent.planner_agent import planner_agent


APP_NAME = "pharma_briefing_agent"
USER_ID = "test_user"
SESSION_ID = "test_session"
MEETING_ID = "mtg_demo_multi_001"


async def main() -> None:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    runner = Runner(
        app_name=APP_NAME,
        agent=planner_agent,
        session_service=session_service,
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text=f"meeting_id: {MEETING_ID}")],
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
