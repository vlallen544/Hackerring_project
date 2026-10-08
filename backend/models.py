# Pydantic schemas shared across the backend (the "shapes" of data agents must return)
from typing import Literal

from pydantic import BaseModel, Field

# ---------- Knowledge Builder output ----------
class Concept(BaseModel):
    id: str = Field(description="snake_case id, e.g. 'window_functions'. Same id for the same idea in every source.")
    name: str = Field(description="Human-readable name, e.g. 'Window Functions'")
    description: str = Field(description="One-sentence description of the concept")

class Claim(BaseModel):
    concept_id: str = Field(description="id of the concept this claim is about")
    statement: str = Field(description="The claim in one short sentence, in your own words")
    quote: str = Field(description="EXACT text copied from the source page that supports the claim (8-30 words)")
    source_id: str = Field(description="Source id from the <<SOURCE id | PAGE n>> header")
    page: int = Field(description="Page number from the <<SOURCE id | PAGE n>> header")
    claim_type: Literal["definition", "fact", "rule", "requirement", "opinion"]

class Prerequisite(BaseModel):
    before: str = Field(description="concept id that must be learned first")
    after: str = Field(description="concept id that depends on it")
    reason: str = Field(description="Why 'before' is needed for 'after'")

class KnowledgeExtraction(BaseModel):
    concepts: list[Concept]
    claims: list[Claim]
    prerequisites: list[Prerequisite]