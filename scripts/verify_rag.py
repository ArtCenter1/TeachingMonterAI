import os
from modules.rag_retriever import retriever
from loguru import logger
from modules.m1_sourcing import SourcingModule

def verify():
    test_queries = {
        "Physics": [
            "What are Newton's Laws?",
            "Explain the first law of thermodynamics",
            "What is constructive interference?",
            "How does a magnetic field affect a moving charge?"
        ],
        "Biology": [
            "What is the structure of DNA?",
            "What happens during mitosis?",
            "How does natural selection work?",
            "Trace the path of blood through the heart"
        ],
        "CS": [
            "What is the difference between an array and a linked list?",
            "Explain how quicksort works",
            "What is encapsulation in OOP?",
            "What is a base case in recursion?"
        ],
        "Mathematics": [
            "How do I find the derivative of x squared?",
            "What is the fundamental theorem of calculus?",
            "Explain Bayes' Theorem",
            "How do I multiply two matrices?"
        ]
    }

    logger.info("--- RAG Coverage & Hit Rate Verification ---")
    
    total_queries = 0
    hits = 0

    for domain, queries in test_queries.items():
        print(f"\n[Domain: {domain}]")
        for query in queries:
            total_queries += 1
            results = retriever.retrieve(query, domain=domain, n_results=1)
            if results and len(results) > 0:
                hits += 1
                print(f"  [OK] Query: '{query}' -> HIT (Length: {len(results[0])} chars)")
            else:
                print(f"  [FAIL] Query: '{query}' -> MISS")

    hit_rate = (hits / total_queries) * 100
    print(f"\nFinal RAG Statistics:")
    print(f"Total Queries: {total_queries}")
    print(f"Total Hits: {hits}")
    print(f"Hit Rate: {hit_rate:.2f}%")

    # Domain Resolution Verification
    print("\n--- Domain Resolution Verification ---")
    sourcing = SourcingModule()
    domain_tests = {
        "Newton's Second Law": "Physics",
        "Genetic Mutations": "Biology",
        "Bubble Sort Algorithm": "CS",
        "Calculus Derivatives": "Mathematics"
    }
    
    for topic, expected in domain_tests.items():
        resolved = sourcing._get_domain_for_topic(topic)
        if resolved == expected:
            print(f"  [OK] Topic: '{topic}' -> {resolved}")
        else:
            print(f"  [FAIL] Topic: '{topic}' -> {resolved} (Expected: {expected})")

    if hit_rate >= 90:
        logger.success("Target hit rate met (>= 90%)!")
    else:
        logger.warning("Target hit rate not met. Consider expanding the corpus.")

if __name__ == "__main__":
    verify()
