import asyncio
from modules.m3_planner import ConceptPlanner
from modules.schemas import StudentModel


async def test_m3():
    planner = ConceptPlanner()
    student_model = StudentModel(
        level="high_school",
        knowledge_embedding=["basic algebra"],
        misconception_risk={"forces": ["force causes motion"]},
        cognitive_load_budget=0.7,
        modality_preference="mixed",
        abstraction_tolerance=0.5,
    )
    topic = "Photosynthesis"
    graph = await planner.plan(topic, student_model)
    print(f"Generated {len(graph.nodes)} nodes for topic '{topic}'")
    for node in graph.nodes:
        print(f"- {node.concept}")


if __name__ == "__main__":
    asyncio.run(test_m3())
