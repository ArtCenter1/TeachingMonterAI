import os
from dotenv import load_dotenv

load_dotenv()

print(f"GOOGLE_API_KEY size: {len(os.getenv('GOOGLE_API_KEY', ''))}")
print(f"OPENROUTER_API_KEY size: {len(os.getenv('OPENROUTER_API_KEY', ''))}")
print(f"SEARCH_API_KEY size: {len(os.getenv('SEARCH_API_KEY', ''))}")
print(f"CARTESIA_API_KEY size: {len(os.getenv('CARTESIA_API_KEY', ''))}")
