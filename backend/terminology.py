"""
Rule-based terminology / controlled-vocabulary compliance checking.

Loads a glossary of {non-standard-or-banned term: preferred term} and flags
every occurrence in the document, with surrounding context so a reviewer can
judge each hit quickly. This is deliberately deterministic (no AI call) so it
is cheap to run on every keystroke or every JIRA/SVN sync in the eventual
Versight middleware pipeline.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_GLOSSARY_PATH = Path(__file__).parent / "config" / "manufacturing_glossary.json"


def load_glossary(path: Path = DEFAULT_GLOSSARY_PATH) -> Dict[str, str]:
    with open(path, "r") as f:
        return json.load(f)


def check_terminology(
    text: str,
    glossary: Dict[str, str],
    overrides: Optional[Dict[str, str]] = None,
) -> List[Dict[str, str]]:
    combined = dict(glossary)
    if overrides:
        combined.update(overrides)

    issues = []
    for banned_term, preferred_term in combined.items():
        if not banned_term or banned_term.strip().lower() == preferred_term.strip().lower():
            continue
        pattern = re.compile(r"\b" + re.escape(banned_term) + r"\b", re.IGNORECASE)
        for match in pattern.finditer(text):
            start = max(match.start() - 30, 0)
            end = min(match.end() + 30, len(text))
            context = text[start:end].replace("\n", " ").strip()
            issues.append({
                "found": match.group(0),
                "preferred": preferred_term,
                "context": f"...{context}...",
            })
    return issues
