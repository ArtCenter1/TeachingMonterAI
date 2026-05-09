import json
from typing import Dict, List, Optional

class AnalogyStore:
    """
    A lightweight retrieval utility managing curated PCK (Pedagogical Content Knowledge) analogies.
    C1 Expansion: 25+ entries per subject, 100+ total.
    """
    def __init__(self):
        # PCK Analogy Store — C1 Expanded 2026-04-22
        self.catalog = {
            "Computer Science": {
                "Recursion": "Like Russian nesting dolls; each doll contains a smaller version of itself, all the way until you reach the smallest one — the base case.",
                "Algorithm": "Like a recipe in a cookbook; a precise, step-by-step set of instructions that always produces the same result if followed correctly.",
                "Self-Attention": "Like highlighting every word in a sentence and asking: 'Which other words help me understand THIS one specifically?'",
                "Array": "Like a row of numbered post-office boxes; you know exactly where to find each letter by its box number.",
                "Loop": "Like running laps on a track; you repeat the same path until a specific condition (finishing your target laps) is met.",
                "Linked List": "Like a scavenger hunt; each clue only tells you where the NEXT clue is. You cannot jump to clue #5 without following the chain from the start.",
                "Sorting": "Like organising a messy hand of playing cards by repeatedly picking two cards, comparing them, and swapping the lower one left.",
                "Encapsulation": "Like a car dashboard; you use the steering wheel and pedals (public interface) without knowing how the combustion engine works (private implementation).",
                "Binary": "Like a row of light switches; each switch is either ON (1) or OFF (0). 8 switches give you 256 combinations.",
                "Time Complexity": "Like an elevator vs. stairs; for 2 floors, stairs (simple loop) is fine. For the 50th floor, elevator (better algorithm) wins. Big O tells you how they scale.",
                "Graph": "Like a map of cities (nodes) connected by roads (edges). Finding the shortest path is literally the same problem GPS solves every day.",
                "BFS": "Like ripples spreading out from a stone dropped in water; you explore all nodes one 'ring' at a time, guaranteeing the shortest hop-count path.",
                "DFS": "Like exploring a maze by always turning left; you go as deep as possible down one path before backtracking.",
                "Dynamic Programming": "Like keeping a notebook of all previously solved sub-problems; instead of recalculating Fibonacci(10) a hundred times, you write it down once.",
                "Hash Table": "Like a library with a clever filing system; instead of searching every shelf, you compute a code from the book title that tells you exactly which shelf it's on.",
                "Stack": "Like a stack of plates; you can only add or remove from the top. Last In, First Out (LIFO).",
                "Queue": "Like a bus queue; the person who arrived first is served first. First In, First Out (FIFO).",
                "Binary Search": "Like finding a word in a printed dictionary; you open to the middle, decide which half contains your word, then repeat — halving the problem each time.",
                "Inheritance": "Like a biological family tree; a Golden Retriever 'inherits' being a Dog, which inherits being a Mammal — getting all the properties of each ancestor.",
                "Polymorphism": "Like a universal charger; it works with a phone, tablet, or laptop (different objects) through the same interface (USB port), but each device handles charging differently.",
                "API": "Like a restaurant menu; you don't need to know how the kitchen works. You just submit an order (request) and receive a result (response).",
                "Concurrency": "Like a chef preparing multiple dishes; they don't clone themselves — they interleave tasks (stirring soup, then checking the oven) so nothing burns.",
                "Machine Learning": "Like teaching a child to recognise cats; you don't program rules. You show thousands of cat photos until patterns emerge in their brain (the model).",
                "Neural Network": "Like a phone tree in an organisation; a signal passes through layers of people, each slightly transforming the message, before a final decision reaches the CEO.",
                "Compilation": "Like translating an entire book from English to French before publication, vs. interpretation (having a live translator read aloud sentence by sentence)."
            },
            "Physics": {
                "Conservation of Momentum": "Like billiard balls; when the cue ball hits the rack, its momentum doesn't vanish — it distributes through all the other balls.",
                "Force": "Not just a push or pull — it's the ONLY thing that can change an object's state of motion. No net force = no change in velocity.",
                "Current vs. Voltage": "Like water in a pipe: Voltage is the water pressure, Current is the flow rate. You can have high pressure (voltage) with a tiny trickle (low current).",
                "Energy": "Like money in different bank accounts; you can transfer it between accounts (forms), but the total sum always stays the same.",
                "Entropy": "Like a tidy bedroom left alone for a month; it naturally drifts toward disorder. It takes deliberate energy input to maintain order.",
                "Wave Properties": "Like the 'Mexican wave' in a stadium; the people (medium) move up and down locally, but the wave pattern itself travels around the whole circle.",
                "Electromagnetism": "Like a dance: a changing electric field creates a magnetic field, which creates an electric field... and the two fields leapfrog through space as light.",
                "Newton's First Law": "Like a hockey puck on frictionless ice; it keeps sliding forever. Friction is the hidden force we overlook in everyday life.",
                "Newton's Third Law": "Like swimming; you push the water backward (action) and the water pushes you forward (reaction) with equal force.",
                "Quantum Superposition": "Like a coin spinning in the air; it's not yet heads or tails — it's in a superposition of both states until it lands (is measured).",
                "Wave-Particle Duality": "Like a dolphin; it swims like a wave through water but is clearly a particle (object) when you pick it up. Context determines which property dominates.",
                "Thermodynamics — 1st Law": "Like a bank account; energy deposited as heat minus work done by the system equals the change in the account balance (internal energy).",
                "Thermodynamics — 2nd Law": "Like mixing coffee and cream; the cream always spreads through the coffee. It never spontaneously un-mixes. Entropy only increases.",
                "Refraction": "Like a lawnmower wheel rolling from grass onto gravel at an angle; the side that hits the gravel first slows down, making the whole mower turn.",
                "Electric Field": "Like the gravitational field of a mountain; you feel a force everywhere around it, even without touching it, with strength decreasing with distance.",
                "Magnetic Field": "Like an invisible set of tension strings radiating from a magnet's poles. A compass needle aligns along the string, pointing from south to north pole.",
                "Resonance": "Like pushing a child on a swing; if you push at exactly the right frequency, small pushes accumulate into large swings. Wrong frequency = wasted effort.",
                "Momentum": "Like a bowling ball vs. a tennis ball at the same speed; the bowling ball is much harder to stop because its momentum (mass × velocity) is far greater.",
                "Circuits (Series vs. Parallel)": "Like water pipes; series is one pipe where blocking one section stops all flow. Parallel gives multiple paths — blocking one still allows flow through others.",
                "Nuclear Fission": "Like splitting a log; you apply a small amount of energy (the axe) to a large, unstable log (heavy nucleus) and release much more energy from the split.",
                "Radioactive Decay": "Like a crowd of people independently flipping coins; at any moment, roughly half will flip heads (decay). The crowd (sample) halves at a predictable rate.",
                "Gravitational Field": "Like a stretched rubber sheet with a bowling ball on it; massive objects warp spacetime, causing other objects to 'fall' toward them along the curves.",
                "Diffraction": "Like sound from an open door; you can hear people talking around a corner because sound bends around the edges of the doorway opening.",
                "Impulse": "Like the difference between catching a ball with a stiff arm vs. letting your arm recoil; the recoil increases the contact time, reducing the peak force.",
                "Refraction (Car on Sand)": "Like a toy car driving from pavement onto sand at an angle; the wheel that hits the sand first slows down, causing the whole car to pivot and change direction.",
                "Total Internal Reflection": "Like a silvered mirror inside a swimming pool; if you look up from underwater at a steep enough angle, the surface stops being a window and starts acting like a perfect mirror.",
                "Convex Lens": "Like a magnifying glass or a 'gathering' tool; it collects wide rays of light and focuses them into a single bright point.",
                "Reflection": "Like a rubber ball bouncing off a wall; the angle it hits the wall is the same as the angle it bounces off."
            },
            "Biology": {
                "DNA Transcription": "Like photocopying a master blueprint; the original (DNA) stays locked in the library (nucleus) and you take only the copy (mRNA) to the construction site (ribosome).",
                "Evolution": "NOT goal-directed — more like a sieve. Random mutations create variation; the environment is the sieve that determines which variants pass through to reproduce.",
                "Cell Membrane": "Like a security bouncer with a guest list; it controls which molecules enter and exit based on specific molecular 'ID checks' (receptor proteins).",
                "Mitochondria": "Like a power station converting raw fuel (glucose from food) into a form of electricity (ATP) that every machine in the factory (cell) can plug into.",
                "Mitosis": "Like a photocopier making a perfect duplicate of a document; the result is two identical copies of the original.",
                "Circulatory System": "Like a city's blood supply and waste management combined; the heart is the pump, arteries are the highways, capillaries are the side streets, veins are the return roads.",
                "Photosynthesis": "Like a solar-powered factory; sunlight (solar energy) drives machines (enzymes) that convert raw materials (CO2 + H2O) into products (glucose + oxygen).",
                "Enzyme": "Like a lock and key; only the correct-shaped substrate (key) fits the enzyme's active site (lock). Temperature and pH can warp the lock, making it non-functional.",
                "Nervous System": "Like a telephone network; sensory neurons are input lines calling head office (brain), which processes the call and sends commands down motor neuron output lines.",
                "Neuron Signalling": "Like a row of dominoes; the electrical impulse doesn't flow like water but instead triggers each section of the membrane to 'fall' in turn.",
                "Natural Selection": "Like a talent show with a brutal judge (the environment); individuals who happen to have the right traits for this judge are most likely to survive and audition again.",
                "Mendelian Genetics": "Like card drawing from two decks; each parent shuffles their deck (alleles) and passes one random card to the child, who gets a hand of two.",
                "Immune System": "Like an army with a memory; the first encounter with an invader (pathogen) is a hard battle. After winning, the army keeps a small trained squad (memory cells) ready for a faster response next time.",
                "Homeostasis": "Like a thermostat in a house; when temperature drops, the heater fires; when it's too hot, the heater shuts off. The body constantly senses and corrects deviations.",
                "Active Transport": "Like moving against a crowd using energy; instead of floating passively downstream (diffusion), active transport uses ATP to push molecules against the concentration gradient.",
                "Ecological Niche": "Like a job in a company; two animals (employees) cannot permanently hold the exact same job (niche) in the same company (ecosystem).",
                "Food Web": "Like a financial market; if one major company (keystone species) collapses, the ripple effects cascade through the entire interconnected economy.",
                "Osmosis": "Like tea bags in hot water; water molecules move from a dilute region (clear water) through a semi-permeable membrane to a concentrated region (inside the bag) to equalise.",
                "Meiosis": "Like shuffling a deck of cards and dealing two different hands; the genetic material is halved and reshuffled, producing four unique gametes.",
                "Endocrine System": "Like sending a memo through company email; hormones (memos) travel in the bloodstream (email network) to specific departments (target organs) that have the right 'inbox' (receptors).",
                "ATP": "Like a rechargeable coin; cells 'spend' the coin (ATP → ADP) to power work, then 'recharge' it using food energy (ADP → ATP) in the mitochondria.",
                "Cell Differentiation": "Like all employees starting with the same contract (stem cell genome) but choosing different departments (liver, neuron, muscle) by turning on and off specific pages.",
                "Virus Replication": "Like a USB drive that hijacks your computer; the virus injects its code (viral RNA/DNA) and forces the host machinery to copy it thousands of times.",
                "Antibiotic Resistance": "Like Darwinian evolution on fast-forward; a few bacteria that happen to resist the drug survive, reproduce, and soon dominate the population.",
                "Ecosystem Services": "Like a free utility company; forests purify water, bees pollinate crops, and soil bacteria recycle nutrients — all without sending a bill."
            },
            "Mathematics": {
                "Derivative": "Like a speedometer vs. an odometer; the odometer (integral) measures total distance travelled; the speedometer (derivative) shows your exact speed at this instant.",
                "Correlation vs. Causation": "Ice cream sales and shark attacks both peak in summer — they're correlated. But ice cream doesn't attract sharks. The common cause is hot weather.",
                "Function": "Like a vending machine; you input one specific code (x-value), and you get exactly one specific result (y-value). Two inputs cannot give the same code for different items.",
                "Integration": "Like slicing a curved shape into infinitely thin rectangular strips and summing their areas — the thinner the slice, the more accurate the total.",
                "Matrix": "Like a camera filter (Instagram filter); you apply the transformation matrix to the original image vector and get a scaled, rotated, or distorted version.",
                "Probability": "Like a weather forecast; 70% chance of rain means if you ran that day a thousand times, it rained on roughly 700 of them — not a promise.",
                "Limit": "Like driving toward a wall but never quite touching it; the value the function APPROACHES as x gets close to a point — even if the function isn't defined right there.",
                "Derivative Chain Rule": "Like converting speed from km/h to m/s by multiplying by a conversion factor; composited rate changes multiply together.",
                "Logarithm": "Like asking 'how many times do I multiply this base to get that number?' log₂(8) = 3 because 2 × 2 × 2 = 8.",
                "Infinity": "Like the horizon; no matter how far you sail toward it, you never reach it. It is a direction, not a destination.",
                "Proof by Contradiction": "Like a lawyer who proves their client was innocent by showing the alternative (guilt) leads to an impossible contradiction.",
                "Vectors": "Like giving directions; 5 km north is completely different from 5 km south, even though both have the same magnitude (5 km). Direction matters.",
                "Complex Numbers": "Like rotating on a 2D plane; multiplying by i is simply a 90° rotation in the complex plane — not mystical, just a different kind of number line.",
                "Standard Deviation": "Like asking 'how far does the typical player's score deviate from the team average?' — a measure of how spread out data is, not just where the middle is.",
                "Bayes' Theorem": "Like updating your belief with new evidence; if you test positive for a rare disease, knowing the test's false-positive rate dramatically changes the real probability you're sick.",
                "Eigenvectors": "Like a door on hinges; when you multiply (transform) it, a door only moves along a fixed axis — it is 'stretched' but never rotated. These special directions are eigenvectors.",
                "Taylor Series": "Like approximating a curved road with a series of straighter and straighter road segments; the more terms you add, the more accurately you trace the original curve.",
                "Modular Arithmetic": "Like a 12-hour clock; after 12, you start again from 1. 11 + 3 = 2 (mod 12). It's arithmetic that 'wraps around'.",
                "Statistical Hypothesis Testing": "Like a criminal trial; you assume innocence (null hypothesis) until the evidence (data) is strong enough to convict (reject H0) beyond reasonable doubt.",
                "Differential Equation": "Like a GPS giving you directions based on where you currently are; the equation defines a rule for how fast something changes, and the solution traces the full journey.",
                "Trigonometry": "Like the shadow of a rotating stick in the sun; as the stick rotates around a point, its shadow length traces out the familiar wave pattern of sine and cosine.",
                "Number Theory — Primes": "Like atoms in chemistry; prime numbers are the indivisible building blocks from which all other whole numbers can be constructed via multiplication.",
                "Fourier Transform": "Like a prism splitting white light into its component colours; the Fourier transform splits a complex signal into its component sine wave frequencies.",
                "Gradient Descent": "Like a hiker in dense fog finding the valley bottom by always stepping downhill; at each point, you take a small step in the steepest downward direction.",
                "Imaginary Unit (i)": "Like inventing a new type of number when you couldn't take the square root of a negative; i = √(-1) expands our number line into a 2D plane."
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
        concept_lower = concept.lower()
        for key, value in self.catalog[subject].items():
            if concept_lower in key.lower() or key.lower() in concept_lower:
                return value
        
        return None

    def get_all_analogies_for_subject(self, subject: str) -> Dict[str, str]:
        """Return all analogies for a given subject."""
        return self.catalog.get(subject, {})

    def count(self) -> Dict[str, int]:
        """Return count of analogies per subject."""
        return {subject: len(entries) for subject, entries in self.catalog.items()}

    def total_count(self) -> int:
        """Return total number of analogies across all subjects."""
        return sum(len(v) for v in self.catalog.values())

# Singleton instance for easy import
analogy_store = AnalogyStore()
