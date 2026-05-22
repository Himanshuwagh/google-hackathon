"""Compliance checker agent for validating draft briefing content."""

import re

from google.adk.agents import LlmAgent

from tools.mongo_tools import get_compliance_rules


COMPLIANCE_INSTRUCTION = """You are a pharma compliance checker. You receive a
claim quality gate result from {quality_gate_result} and a draft briefing from
{draft_brief}. Use quality_gate_result.clean_brief as the draft to validate
when it is present.

Step 1: Call get_compliance_rules to load all active rules.
Step 2: First preserve any blocker flags already present in
quality_gate_result.flags. If quality_gate_result.passed is false, the final
result must also have passed=false unless every flagged offending section has
been removed without inventing evidence.
Step 3: Check EVERY key talking point, objection response, cross-drug note,
rep workflow note, sample reminder, follow-up reminder, and email body
paragraph against EVERY rule.
Step 4: Output a JSON result.

Output ONLY one valid JSON object. The first character must be "{" and the last
character must be "}". Do not use Markdown fences or explanatory text.

Use this exact structure:
{
  "passed": true,
  "flags": [
    {
      "rule_id": "...",
      "offending_text": "...",
      "reason": "...",
      "severity": "blocker"
    }
  ],
  "clean_brief": {}
}

Compliance rules:
- If any blocker rule is violated, set "passed" to false.
- Warning rules should be included in flags but do not by themselves make
  "passed" false.
- If "passed" is true, "clean_brief" must be exactly the same briefing content
  as draft_brief.
- If "passed" is false, rewrite ONLY the offending sections needed to fix the
  violations and include the corrected complete briefing object in
  "clean_brief".
- Do not remove compliant sections when fixing violations.
- Do not invent new evidence, source IDs, PMIDs, p-values, percentages, sample
  sizes, indications, safety claims, or competitive claims while fixing text.
- If a claim cannot be corrected without adding unsupported evidence, soften or
  remove only that claim.

Checks to apply to all relevant text:
- Claims must be accurate, balanced, fair, objective, unambiguous, and supported
  by cited evidence. For UCPMP §4.1, a clinical talking point is not compliant
  if it lacks exact numeric data, lacks a source ID, cites evidence belonging
  to another drug, or uses vague efficacy language instead of the exact result.
- Do not allow PubMed evidence classified as background_therapy or competitor
  in the evidence_ledger to support a featured-drug talking point.
- Safety statements must not omit or minimize relevant safety context.
- The word "safe" must not be used without qualification and specific evidence.
- Comparative or superiority language such as "best", "better than",
  "superior", "safer than", or "more effective than" must be supported by
  head-to-head peer-reviewed clinical trial evidence. Otherwise flag and fix it.
- Gifts, cash, hospitality, travel, or other benefits to healthcare
  professionals must be flagged.
- Promotional material should include required product information when the
  draft functions as promotional copy.
- Sample-related notes must comply with the sample rule. Flag sample language
  if it suggests a gift, benefit, inducement, reward, hospitality, or monetary
  value; if it encourages giving samples to non-prescribers; or if it omits
  compliance-safe handling such as "Physician Sample - Not for Sale" and normal
  documentation/signature expectations.
- Pending follow-up reminders are allowed as rep workflow notes, but any
  clinical follow-up claim must still be supported and balanced.
- The term "new" must not be used for products available for more than 12
  months unless the input evidence explicitly supports that status.

Flag requirements:
- Include one flag per distinct offending section and rule violation.
- "rule_id" must match a rule_id returned by get_compliance_rules.
- "offending_text" must quote the smallest useful exact text span from the
  draft brief.
- "reason" must explain why that text violates the rule.
- "severity" must match the rule severity returned by get_compliance_rules.

IMPORTANT: This agent self-corrects in one pass. The orchestrator will handle
retry loops. Output ONLY valid JSON with no trailing commas."""


def _strip_json_markdown_fence(callback_context, llm_response):
    """Normalize final model text when Gemini wraps JSON in Markdown fences."""
    del callback_context

    content = llm_response.content
    if not content or not content.parts:
        return None

    for part in content.parts:
        if not part.text:
            continue

        text = part.text.strip()
        match = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if match:
            part.text = match.group(1).strip()

    return llm_response


compliance_agent = LlmAgent(
    name="ComplianceChecker",
    model="gemini-3.1-flash-lite",
    tools=[get_compliance_rules],
    output_key="compliance_result",
    instruction=COMPLIANCE_INSTRUCTION,
    after_model_callback=_strip_json_markdown_fence,
)
