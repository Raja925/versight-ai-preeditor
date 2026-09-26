"""
Rule-based template/structure compliance checking.

Given a document type (SOP, Work Instruction, Change Notice, ...), loads the
required section list from config/sop_template.json and checks the document
text for headers that match each required section, flagging anything missing
or out of order. Header detection is heuristic (numbered or all-caps or
Title Case short lines) since source documents arrive as plain text/Word
exports rather than structured markup.
"""
import json
import re
from pathlib import Path
from typing import List, Dict

DEFAULT_TEMPLATE_PATH = Path(__file__).parent / "config" / "sop_template.json"

HEADER_PATTERN = re.compile(
    r"^\s{0,3}(#{1,3}\s*)?(\d+[\.\)]?\s*)?([A-Z][A-Za-z0-9 /&\-]{2,60})\s*:?\s*$"
)


def load_template(document_type: str, path: Path = DEFAULT_TEMPLATE_PATH) -> List[str]:
    with open(path, "r") as f:
        templates = json.load(f)
    return templates.get(document_type, templates.get("default", []))


def extract_headers(text: str) -> List[str]:
    headers = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m = HEADER_PATTERN.match(stripped)
        if m and m.group(3):
            candidate = m.group(3).strip()
            if len(candidate.split()) <= 6:
                headers.append(candidate)
    return headers


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def check_structure(text: str, required_sections: List[str]) -> Dict:
    found_headers = extract_headers(text)
    normalized_found = [normalize(h) for h in found_headers]

    missing = []
    match_positions = []
    for req in required_sections:
        norm_req = normalize(req)
        match_index = None
        for i, nf in enumerate(normalized_found):
            if norm_req and (norm_req in nf or nf in norm_req):
                match_index = i
                break
        if match_index is None:
            missing.append(req)
        else:
            match_positions.append(match_index)

    out_of_order = match_positions != sorted(match_positions)

    notes = []
    if missing:
        notes.append(f"{len(missing)} required section(s) not detected: {', '.join(missing)}")
    if out_of_order:
        notes.append("Detected sections appear out of the expected order.")
    if not missing and not out_of_order:
        notes.append("All required sections present and in expected order.")

    return {
        "required_sections": required_sections,
        "found_sections": found_headers,
        "missing_sections": missing,
        "out_of_order": out_of_order,
        "notes": notes,
    }
