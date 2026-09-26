from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class AnalyzeRequest(BaseModel):
    text: str = Field(..., description="The document text to analyze")
    document_type: str = Field(
        default="SOP",
        description="Type of document, e.g. SOP, Work Instruction, Change Notice",
    )
    glossary_overrides: Optional[Dict[str, str]] = Field(
        default=None,
        description="Additional non-standard-term -> preferred-term mappings, merged over the default glossary",
    )
    required_sections: Optional[List[str]] = Field(
        default=None,
        description="Override the required section list for structure checking",
    )
    skip_ai_review: bool = Field(
        default=False,
        description="Skip the Claude API call and return rule-based checks only",
    )


class ReadabilityResult(BaseModel):
    flesch_kincaid_grade: float
    avg_sentence_length: float
    passive_voice_sentences: List[str]
    long_sentences: List[str]


class TerminologyIssue(BaseModel):
    found: str
    preferred: str
    context: str


class StructureResult(BaseModel):
    required_sections: List[str]
    found_sections: List[str]
    missing_sections: List[str]
    out_of_order: bool
    notes: List[str]


class AISuggestion(BaseModel):
    category: str
    severity: str
    location: str
    issue: str
    suggestion: str


class AnalyzeResponse(BaseModel):
    document_type: str
    readability: ReadabilityResult
    terminology_issues: List[TerminologyIssue]
    structure: StructureResult
    ai_suggestions: List[AISuggestion]
    overall_score: float
    summary: str
