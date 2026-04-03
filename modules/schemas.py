from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any
from enum import Enum
import json

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
    course_requirement: str = Field(..., description="Topic or course requirement")
    student_persona: str = Field(..., description="Student description or persona")
    model_override: Optional[str] = None
    age_group: Optional[str] = "10-15"
    
    # Per-request overrides for Search and AI
    google_api_key: Optional[str] = None
    search_cx: Optional[str] = None
    search_api_key: Optional[str] = None

    class Config:
        extra = "allow" # Stop 422 errors for any extra fields sent by UI

    @model_validator(mode='before')
    @classmethod
    def map_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # 1. Map 'topic' or 'requirement' to 'course_requirement'
            for alt in ["topic", "requirement"]:
                if alt in data and ("course_requirement" not in data or not data["course_requirement"]):
                    data["course_requirement"] = data[alt]
            
            # 2. Map 'persona' or 'student_model' to 'student_persona'
            for alt in ["persona", "student_model"]:
                if alt in data and ("student_persona" not in data or not data["student_persona"]):
                    val = data[alt]
                    # If it's a dict (common in UI), flatten it to a string for the pipeline
                    if isinstance(val, dict):
                        data["student_persona"] = json.dumps(val)
                    else:
                        data["student_persona"] = str(val)
            
            # 3. Ensure mandatory fields exist for validation
            if "course_requirement" not in data:
                data["course_requirement"] = "General Topic"
            if "student_persona" not in data:
                data["student_persona"] = "General Learner"
                
        return data

class GenerationResponse(BaseModel):
    video_url: str
    subtitle_url: Optional[str] = None
    supplementary_url: Optional[str] = None
    generation_time_seconds: int

class FactBundle(BaseModel):
    facts: List[Dict[str, Any]]
    study_guide_url: Optional[str] = None
