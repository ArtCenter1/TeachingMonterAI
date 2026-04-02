from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class StudentLevel(str, Enum):
    IB = "IB"
    AP = "AP"
    HIGH_SCHOOL = "high_school"
    MIDDLE_SCHOOL = "middle_school"

class ModalityPreference(str, Enum):
    VISUAL = "visual"
    VERBAL = "verbal"
    MIXED = "mixed"

class StudentModel(BaseModel):
    level: StudentLevel = Field(..., description="Educational level of the student")
    knowledge_embedding: List[str] = Field(default_factory=list, description="Implied known concepts")
    misconception_risk: Dict[str, List[str]] = Field(default_factory=dict, description="Top-3 likely errors by concept")
    cognitive_load_budget: float = Field(..., description="Max concept density ceiling")
    modality_preference: ModalityPreference = Field(..., description="Preferred learning modality")
    abstraction_tolerance: float = Field(..., description="0=concrete only, 1=fully abstract")

class ConceptNode(BaseModel):
    concept: str
    prerequisites: List[str]
    misconceptions: List[str]
    visual_type: str = Field(..., description="Optimal visual representation (e.g. animation, flowchart)")
    duration_minutes: float

class ConceptGraph(BaseModel):
    nodes: List[ConceptNode]
    total_duration_minutes: float

class ScriptSegment(BaseModel):
    segment_id: str
    concept: str
    narration: str
    visual_type: str
    visual_content_spec: str
    duration_seconds: float
    citations: List[Dict[str, str]] = Field(default_factory=list)

class FullScript(BaseModel):
    title: str
    scaffolding_strategy: str
    segments: List[ScriptSegment]
    hook: str
    checks: List[str] = Field(default_factory=list, description="Socratic question prompts")

class CIDPPScores(BaseModel):
    clarity: int = Field(ge=1, le=10)
    integrity: int = Field(ge=1, le=10)
    depth: int = Field(ge=1, le=10)
    practicality: int = Field(ge=1, le=10)
    pertinence: int = Field(ge=1, le=10)
    revisions: List[str] = Field(default_factory=list)

class GenerationRequest(BaseModel):
    course_requirement: str
    student_persona: str

class GenerationResponse(BaseModel):
    video_url: str
    subtitle_url: Optional[str] = None
    supplementary_url: Optional[str] = None
    generation_time_seconds: int

class FactBundle(BaseModel):
    facts: List[Dict[str, Any]]
    study_guide_url: Optional[str] = None
