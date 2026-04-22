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
                "Loop": "Like running around a track until you've finished your 5 laps; you repeat the same path until a condition is met.",
                "Linked List": "Like a scavenger hunt; each clue tells you where to find the next one, but you can't jump to the middle without following the chain.",
                "Sorting": "Like organizing a messy deck of cards by constantly comparing two cards and deciding which one is 'higher'.",
                "Encapsulation": "Like a car dashboard; you can use the steering wheel and pedals (public interface) without needing to know how the engine works (private implementation).",
                "Binary": "Like a series of light switches; each one is either ON (1) or OFF (0)."
            },
            "Physics": {
                "Conservation of Momentum": "Like billiard balls hitting each other; or an ice skater pulling their arms in to spin faster.",
                "Force": "A push or a pull that can change an object's motion.",
                "Current vs. Voltage": "Like water in a pipe: Voltage is the pressure pushing the water, and Current is the actual flow of water.",
                "Energy": "Like money in a bank; you can store it, spend it, and change its form, but the total amount follows strict rules.",
                "Entropy": "Like a tidy room that naturally gets messy over time unless you put energy into cleaning it up.",
                "Wave Properties": "Like a 'sports wave' in a stadium; the people (medium) move up and down, but the wave (energy) moves around the whole circle.",
                "Electromagnetism": "Like a dance between two invisible partners (electric and magnetic fields) where one's movement always pulls the other along."
            },
            "Biology": {
                "DNA Transcription": "Like photocopying a master blueprint without taking the original out of the secure library (the nucleus).",
                "Evolution": "NOT goal-directed; more like a filter where only the shapes that fit through the current holes make it to the next generation.",
                "Cell Membrane": "Like a security guard at a club; it decides who 'gets in' and who 'stays out' based on specific markers.",
                "Mitochondria": "The 'powerhouse' of the cell, converting fuel (glucose) into usable energy (ATP).",
                "Mitosis": "Like a business opening a perfect clone of its first office; everything is copied exactly so the new branch functions identically.",
                "Circulatory System": "Like a city's plumbing and delivery system combined; the heart is the pump, and the blood is the delivery trucks."
            },
            "Mathematics": {
                "Derivative": "Like a speedometer reading (speed at this exact moment) vs. an odometer (distance traveled over time).",
                "Correlation vs. Causation": "Just because ice cream sales and shark attacks both go up in summer doesn't mean eating ice cream causes shark attacks. They both have a common cause: the heat!",
                "Function": "Like a vending machine: you put in a specific code (input), and you get exactly one specific snack (output) back.",
                "Integration": "Like slicing a loaf of bread into infinitely thin pieces and adding them all up to find the total volume.",
                "Matrix": "Like a camera filter; you apply the filter (matrix) to the original image (vector) to get a transformed version.",
                "Probability": "Like a weather forecast; it doesn't tell you exactly what will happen, but it helps you decide whether to bring an umbrella."
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
