import asyncio
from modules.m2_persona import PersonaParser


async def test_m2():
    parser = PersonaParser()
    personas = [
        "High school student learning biology for the first time",
        "Education Level: Working professional without relevant background | Learning Motivation: Research papers | Focus Level: Low | Depth Preference: Principles-first",
        "A curious 5-year old who loves plants",
    ]
    for persona in personas:
        model = await parser.parse(persona)
        print(f"Persona: {persona}")
        print(f"Level: {model.level}")
        print(f"Knowledge: {model.knowledge_embedding}")
        print(f"Misconceptions: {model.misconception_risk}")
        print(f"Cognitive load: {model.cognitive_load_budget}")
        print(f"Modality: {model.modality_preference}")
        print(f"Abstraction: {model.abstraction_tolerance}")
        print("---")


if __name__ == "__main__":
    asyncio.run(test_m2())
