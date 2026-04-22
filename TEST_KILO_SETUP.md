# How to Test Your Kilo Model Setup

## Step 1: Verify Kilo API Key is Loaded
Run this command to check if your Kilo API key is properly loaded:
```bash
docker exec teaching-monster-app python -c "
import os
from modules.llm_client import get_kilo_pool
pool = get_kilo_pool()
print('KILO_API_KEY present:', bool(os.getenv('KILO_API_KEY')))
print('Kilo pool keys:', len(pool._entries))
if pool._entries:
    print('First key state:', pool._entries[0].state)
"
```

## Step 2: Test Direct Kilo Model Access
Test if a Kilo model works by using the model_override parameter:
```bash
docker exec teaching-monster-app python -c "
import asyncio
from modules.llm_client import LLMClient

async def test():
    client = LLMClient()
    # Try to use your Kilo model directly
    try:
        result = await client.generate_text(
            'Say hello in one sentence', 
            model_override='kilo/x-ai/grok-beta',  # Use your actual model ID here
            model_size='large'
        )
        print('SUCCESS: Kilo model worked!')
        print('Response:', result[:100])
    except Exception as e:
        print('FAILED: Kilo model error:', str(e))

asyncio.run(test())
"
```

## Step 3: Check What Models Are Actually Available
Since we don't know the exact model IDs available through your Kilo account, let's discover them:

### Option A: Check Kilo Dashboard
1. Go to https://kilo.ai
2. Log in with your account
3. Navigate to "Models & Providers" or "Gateway"
4. Look for available xAI/Grok models - they should appear as `kilo/x-ai/grok-*` or similar

### Option B: Test Common Patterns
Try these common model ID patterns:
- `kilo/x-ai/grok-beta`
- `kilo/x-ai/grok-4.1-fast`
- `kilo/x-ai/grok-4.20-reasoning`
- `kilo/x-ai/grok-code-fast-1`
- `kilo/x-ai/grok-vision-beta`

## Step 4: Update .env with Working Model
Once you find a working model ID, update your .env:
```
# For contest mode:
PRIMARY_MODEL=kilo/x-ai/your-working-model
FALLBACK_MODEL=kilo/x-ai/your-backup-model
SYNTHETIC_STUDENT_MODEL=kilo/x-ai/your-working-model
```

## Step 5: Full Pipeline Test
After confirming the Kilo model works, test the full pipeline:
```bash
# Trigger a generation
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"course_requirement": "Test topic", "student_persona": "Test student"}'
```

## Expected Outcome:
- If Kilo model works: You'll see successful generation using your Kilo API key
- If it falls back to Gemini: Check the error to determine why Kilo model failed
- Key rotation should ONLY happen if your Kilo key has issues (quota, invalid key, etc.)

## Troubleshooting:
- "400 - not a valid model ID": The model ID is incorrect for Kilo Gateway
- "401/403": Authentication issue with your Kilo API key
- "404": Model not found in Kilo's catalog
- "429": Rate limit on your Kilo key

Let me know what error you get when testing the Kilo model directly, and I'll help you find the correct model ID.