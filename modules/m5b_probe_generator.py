import os
import json
from typing import List, Optional
from loguru import logger
from .schemas import FactBundle, ConceptGraph, ComprehensionProbe
from .llm_client import LLMClient
from .utils import extract_json

class ProbeGenerator:
    def __init__(self):
        self.client = LLMClient()
        logger.info("ProbeGenerator (M5b) initialized")

    async def generate(
        self,
        fact_bundle: FactBundle,
        concept_graph: ConceptGraph,
        model_override: Optional[str] = None
    ) -> List[ComprehensionProbe]:
        """
        Generates 3 comprehension questions directly from the FactBundle (M1 ground truth).
        """
        if not fact_bundle or not fact_bundle.facts:
            logger.warning("[RLT] No facts available to generate probes.")
            return []

        # Select top 5 facts by length (heuristic for info density) to give LLM context
        sorted_facts = sorted(fact_bundle.facts, key=lambda x: len(x.get("claim", "")), reverse=True)
        top_facts = sorted_facts[:5]
        
        facts_text = "\n".join([f"- {f.get('claim')}" for f in top_facts])
        
        prompt = f"""
        Act as a professional educational assessment designer.
        Given these curriculum facts about the lesson topic:
        
        <facts>
        {facts_text}
        </facts>
        
        Write exactly 3 comprehension questions to test whether a student understood these core facts after watching a video lesson.
        
        Requirements for each question:
        - "question": The clear, concise question text.
        - "correct_answer": A 1-3 word key phrase or term that MUST appear in a correct answer (e.g. "ATP", "F=ma", "Natural Selection").
        - "concept": The specific concept or fact being tested.
        
        Return ONLY a JSON array of 3 objects.
        """

        try:
            logger.info("[RLT] Generating 3 comprehension probes...")
            response_text = await self.client.generate_text(
                prompt,
                system_instruction="You are an expert in pedagogical assessment. Return ONLY raw JSON.",
                model_size="medium",
                temperature=0.1,
                model_override=model_override
            )
            
            data = extract_json(response_text)
            if not isinstance(data, list):
                raise ValueError("LLM returned JSON that is not a list")
                
            probes = []
            for item in data[:3]: # Ensure max 3
                probes.append(ComprehensionProbe(
                    question=item.get("question", ""),
                    correct_answer=item.get("correct_answer", ""),
                    concept=item.get("concept", "")
                ))
                
            logger.success(f"[RLT] Successfully generated {len(probes)} probes.")
            return probes

        except Exception as e:
            logger.error(f"[RLT] Probe generation failed: {e}")
            return []

# Singleton instance
probe_gen = ProbeGenerator()
