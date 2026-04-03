import json
from typing import Dict, List, Optional

class AnalogyStore:
    """
    A lightweight retrieval utility managing curated PCK (Pedagogical Content Knowledge) analogies.
    Seed data from PRD v1.0.
    """
    def __init__(self):
        # PCK Analogy Store - Seeded from PRD Layer 4.2
        self.catalog = {
            "Computer Science": {
                "Recursion": "Like Russian nesting dolls; or two mirrors facing each other where each reflection contains a smaller reflection.",
                "Algorithm": "Like a recipe in a cookbook; a step-by-step set of instructions to get a specific result.",
                "Self-Attention": "Like highlighting every word in a sentence and asking: 'Which other words help me understand this one specifically?'",
                "Array": "Like a row of numbered lockers; you know exactly where to find each item by its number.",
                "Loop": "Like running around a track until you've finished your 5 laps; you repeat the same path until a condition is met."
            },
            "Physics": {
                "Conservation of Momentum": "Like billiard balls hitting each other; or an ice skater pulling their arms in to spin faster.",
                "Force": "A push or a pull that can change an object's motion.",
                "Current vs. Voltage": "Like water in a pipe: Voltage is the pressure pushing the water, and Current is the actual flow of water.",
                "Energy": "Like money in a bank; you can store it, spend it, and change its form, but the total amount follows strict rules."
            },
            "Biology": {
                "DNA Transcription": "Like photocopying a master blueprint without taking the original out of the secure library (the nucleus).",
                "Evolution": "NOT goal-directed; more like a filter where only the shapes that fit through the current holes make it to the next generation.",
                "Cell Membrane": "Like a security guard at a club; it decides who 'gets in' and who 'stays out' based on specific markers.",
                "Mitochondria": "The 'powerhouse' of the cell, converting fuel (glucose) into usable energy (ATP)."
            },
            "Mathematics": {
                "Derivative": "Like a speedometer reading (speed at this exact moment) vs. an odometer (distance traveled over time).",
                "Correlation vs. Causation": "Just because ice cream sales and shark attacks both go up in summer doesn't mean eating ice cream causes shark attacks. They both have a common cause: the heat!",
                "Function": "Like a vending machine: you put in a specific code (input), and you get exactly one specific snack (output) back."
            }
        }

    def get_analogy(self, subject: str, concept: str) -> Optional[str]:
        """Retrieve an analogy by subject and concept keywords."""
        if subject not in self.catalog:
            return None
        
        # Exact match
        if concept in self.catalog[subject]:
            return self.catalog[subject][concept]
        
        # Keyword match (fuzzy)
        for key, value in self.catalog[subject].items():
            if key.lower() in concept.lower() or concept.lower() in key.lower():
                return value
        
        return None

# Singleton instance
analogy_store = AnalogyStore()
