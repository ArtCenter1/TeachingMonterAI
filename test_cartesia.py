import os
import asyncio
from cartesia import Cartesia

async def test_cartesia():
    client = Cartesia(api_key=os.environ.get("CARTESIA_API_KEY"))
    voice_id = "cec7cae1-ac8b-4a59-9eac-ec48366f37ae"
    print("Testing Cartesia Websocket v3...")
    segment_audio_data = b""
    try:
        with client.tts.websocket_connect() as connection:
            ctx = connection.context(
                model_id="sonic-english",
                voice={"mode": "id", "id": voice_id},
                output_format={"container": "raw", "encoding": "pcm_s16le", "sample_rate": 44100},
            )

            # My fix syntax for send():
            ctx.send(
                model_id="sonic-english",
                voice={"mode": "id", "id": voice_id},
                transcript="Hello world, this is a test",
                continue_=False,
                add_timestamps=True
            )

            if hasattr(ctx, "receive"):
                for response in ctx.receive():
                    print("- Received packet type:", response.type)
            else:
                for response in ctx:
                    print("- Received packet (iterator)")
            print("Done")
    except Exception as e:
        print(f"Error: {repr(e)}")

asyncio.run(test_cartesia())
