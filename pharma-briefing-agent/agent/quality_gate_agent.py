"""Deterministic claim quality gate for grounded briefing drafts."""

from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from tools.evidence_grounding import dump_json, parse_json_if_possible, validate_claim_quality


class ClaimQualityGateAgent(BaseAgent):
    """Validates draft claims before compliance review."""

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        draft_brief = parse_json_if_possible(ctx.session.state.get("draft_brief"))
        retrieved_context = parse_json_if_possible(ctx.session.state.get("retrieved_context"))
        result = validate_claim_quality(draft_brief, retrieved_context)
        result_text = dump_json(result)

        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            content=types.Content(role="model", parts=[types.Part(text=result_text)]),
            actions=EventActions(
                state_delta={
                    "quality_gate_result": result_text,
                    "draft_brief": dump_json(result.get("clean_brief", draft_brief)),
                }
            ),
        )


claim_quality_gate = ClaimQualityGateAgent(
    name="ClaimQualityGate",
    description="Deterministically validates numeric evidence and source ownership for briefing claims.",
)
