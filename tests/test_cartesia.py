import os
import wave
from cartesia import Cartesia
from dotenv import load_dotenv
from loguru import logger

def test_cartesia():
    load_dotenv()
    api_key = os.getenv("CARTESIA_API_KEY")
    if not api_key:
        logger.error("CARTESIA_API_KEY not found in .env")
        return

    client = Cartesia(api_key=api_key)
    voice_id = "cec7cae1-ac8b-4a59-9eac-ec48366f37ae"
    transcript = "This is a test of the Teaching Monster AI video generation pipeline audio module."
    output_path = "temp/test_audio.wav"
    os.makedirs("temp", exist_ok=True)

    logger.info("Connecting to Cartesia WebSocket...")
    audio_data = b""
    try:
        with client.tts.websocket_connect() as connection:
            ctx = connection.context()
            
            ctx.send(
                model_id="sonic-english",
                transcript=transcript,
                voice={"mode": "id", "id": voice_id},
                output_format={"container": "raw", "encoding": "pcm_s16le", "sample_rate": 44100},
                end_of_stream=True
            )
            
            for response in connection:
                if response.type == "chunk":
                    if response.audio:
                        audio_data += response.audio
                    logger.info("Received audio chunk")
                elif response.type == "error":
                    logger.error(f"WebSocket Error: {response.error}")
                    break
                elif getattr(response, "done", False):
                    break
        
        if audio_data:
            with wave.open(output_path, "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(44100)
                f.writeframes(audio_data)
            logger.info(f"Test successful! Audio saved to {output_path}")
        else:
            logger.error("No audio data received.")
            
    except Exception as e:
        logger.exception(f"Test failed: {e}")

if __name__ == "__main__":
    test_cartesia()
