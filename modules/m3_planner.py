from typing import List
from .schemas import ConceptNode, ConceptGraph, StudentModel

class ConceptPlanner:
    async def plan(self, topic: str, student_model: StudentModel) -> ConceptGraph:
        # Placeholder for concept sequencing
        # In PRD, this sequences nodes based on ZPD
        return ConceptGraph(
            nodes=[
                ConceptNode(
                    concept=f"Intro to {topic}",
                    prerequisites=[],
                    misconceptions=[],
                    visual_type="Metaphor Animation",
                    duration_minutes=2.0
                ),
                ConceptNode(
                    concept=f"Fundamental of {topic}",
                    prerequisites=[f"Intro to {topic}"],
                    misconceptions=["Intro Misconception"],
                    visual_type="Geometric Animation",
                    duration_minutes=5.0
                )
            ],
            total_duration_minutes=7.0
        )
