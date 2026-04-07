from google import genai
import os

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("ERROR: GOOGLE_API_KEY not set")
else:
    client = genai.Client(api_key=api_key)
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", [])
        if "generateContent" in actions:
            print(m.name)
