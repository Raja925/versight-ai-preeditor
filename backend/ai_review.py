"""
AI-assisted clarity/ambiguity/safety review — the actual "pre-editor" part.

The rule-based passes (readability.py, terminology.py, structure.py) catch
mechanical issues cheaply and deterministically. This module hands the
document, plus a summary of what the rule-based passes already found, to
Claude and asks it to focus specifically on what those passes cannot see:
procedural ambiguity, missing safety context, and internal inconsistency.

Requires ANTHROPIC_API_KEY to be set. If it isn't, analysis still runs with
rule-based checks only (see main.py) — this keeps the tool usable without an
API key, and cheap to run on every save if a caller wants to skip AI review.
"""
import os
import json
from typing import List, Dict, Any

try:
    import anthropic
except ImportError:  # pragma: no cover - handled gracefully at runtime
    anthropic = None

SYSTEM_PROMPT = """You are an AI pre-editor for manufacturing technical documentation \
(SOPs, work instructions, change notices) at a high-volume production facility.
You review procedural text for clarity, safety-critical ambiguity, and internal \
consistency issues that automated rule-based checks cannot catch.
You are precise, terse, and grounded only in the document text provided.
Never invent facts, tolerances, or part numbers that are not in the text.
Return ONLY valid JSON matching the schema you are given, with no prose before or after."""

RESPONSE_SCHEMA_HINT = """Return a JSON array of suggestion objects, each with these fields:
- category: one of "clarity", "ambiguity", "safety", "consistency", "completeness"
- severity: one of "low", "medium", "high"
- location: a short quote (max ~12 words) from the document identifying where the issue is
- issue: one sentence describing the problem
- suggestion: one sentence with a concrete rewrite or fix

If the document has no issues worth flagging, return an empty array [].
Do not flag purely stylistic preferences already covered by grammar or terminology checks;
focus on procedural clarity, ambiguity a technician on the floor could misread, and
safety-relevant gaps."""

DEFAULT_MODEL = os.environ.get("VERSIGHT_MODEL", "claude-sonnet-4-5")


def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or anthropic is None:
        return None
    return anthropic.Anthropic(api_key=api_key)


def run_ai_review(text: str, document_type: str, rule_based_findings: Dict[str, Any]) -> List[Dict[str, Any]]:
    client = get_client()
    if client is None:
        return []

    findings_summary = json.dumps({
        "readability": rule_based_findings.get("readability", {}),
        "terminology_issues": rule_based_findings.get("terminology_issues", []),
        "structure": rule_based_findings.get("structure", {}),
    }, indent=2)

    user_prompt = f"""Document type: {document_type}

Rule-based findings already surfaced (do not repeat these, focus on what they miss):
{findings_summary}

Document text:
---
{text}
---

{RESPONSE_SCHEMA_HINT}"""

    try:
        message = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:]
        suggestions = json.loads(raw)
        if isinstance(suggestions, dict):
            suggestions = suggestions.get("suggestions", [])
        return suggestions
    except Exception as e:
        return [{
            "category": "system",
            "severity": "low",
            "location": "",
            "issue": f"AI review unavailable: {e}",
            "suggestion": "Check ANTHROPIC_API_KEY and network access, or rerun with skip_ai_review=true.",
        }]
