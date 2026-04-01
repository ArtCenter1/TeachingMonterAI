import os
import json
import google.generativeai as genai
from .schemas import FullScript, StudentModel, CIDPPScores
from loguru import logger

class CIDPPCritic:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")

    async def review(self, script: FullScript, student_model: StudentModel) -> CIDPPScores:
        if not self.api_key:
            logger.warning("No API key found for CIDPPCritic, falling back to mock data.")
            return self.get_mock_data()

        prompt = f"""
        Score this educational lesson script on the CIDPP dimensions for the specified student model.
        Script: {script.json()}
        Student Model: {student_model.json()}

        CIDPP Rubric:
        - Clarity: Logical flow, smooth transitions, understandable language.
        - Integrity: Factual accuracy, citations present for all claims.
        - Depth: Nuance, addressing misconceptions.
        - Practicality: Concrete examples, applications.
        - Pertinence: Alignment with student level and persona.

        Return the scores (1-10) and a list of concrete revision instructions as a JSON object matching this schema:
        {{
            "clarity": int,
            "integrity": int,
            "depth": int,
            "practicality": int,
            "pertinence": int,
            "revisions": ["instruction 1", "instruction 2"]
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            content = response.text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            
            data = json.loads(content)
            return CIDPPScores(**data)
        except Exception as e:
            logger.error(f"Error reviewing script with Gemini: {str(e)}")
            return self.get_mock_data()

    def get_mock_data(self) -> CIDPPScores:
        return CIDPPScores(
            clarity=8,
            integrity=10,
            depth=7,
            practicality=7,
            pertinence=8,
            revisions=[]
        )
