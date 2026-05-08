import asyncio
import edge_tts
import os

async def test():
    text = "Vector addition means placing arrows tip to tail. The resultant vector shows the combined effect."
    voice = "en-US-AriaNeural"
    mp3_path = "temp/edge_tts_test.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(mp3_path)
    size = os.path.getsize(mp3_path)
    print(f"OK — Edge TTS generated {size} bytes at {mp3_path}")

asyncio.run(test())
