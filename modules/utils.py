import json
import re
from typing import Dict, Any

def extract_json(text: str) -> Dict[str, Any]:
    """Extract a JSON object from a string that might contain other text."""
    # Attempt to find JSON block in triple backticks (with or without 'json' language specifier)
    pattern = r"```(?:json)?\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(1)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
            
    # Fallback: Find the first { or [ and last } or ]
    start_obj = text.find('{')
    start_arr = text.find('[')
    
    # Determine the earliest starting bracket
    start = -1
    if start_obj != -1 and start_arr != -1:
        start = min(start_obj, start_arr)
    elif start_obj != -1:
        start = start_obj
    elif start_arr != -1:
        start = start_arr
        
    if start != -1:
        # Match the ending bracket based on the starting bracket
        end = text.rfind('}') if text[start] == '{' else text.rfind(']')
        if end != -1 and end > start:
            content = text[start:end+1]
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                try:
                    # Try a slightly more aggressive cleanup for multi-line strings
                    cleaned = re.sub(r'\s+', ' ', content)
                    return json.loads(cleaned)
                except:
                    pass

    raise ValueError(f"Could not extract valid JSON from text: {text[:200]}...")

def infer_subject(course_requirement: str) -> str:
    """Infer subject from course_requirement using keyword heuristics.
    
    Returns standard subject names like 'Physics', 'Biology', 'CS', 'Mathematics', or 'General'.
    """
    req_lower = course_requirement.lower()
    for kw, subj in [
        ("physics", "Physics"), ("biology", "Biology"),
        ("computer", "CS"), ("math", "Mathematics"),
        ("cell", "Biology"), ("momentum", "Physics"),
        ("algorithm", "CS"), ("derivative", "Mathematics"),
        ("recursion", "CS"), ("dna", "Biology"),
        ("force", "Physics"), ("calculus", "Mathematics"),
        ("chemistry", "Chemistry"), ("chemical", "Chemistry"),
    ]:
        if kw in req_lower:
            return subj
    return "General"
