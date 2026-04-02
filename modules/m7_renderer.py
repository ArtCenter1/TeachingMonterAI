import os
import asyncio
import subprocess
from typing import List, Dict, Any
from cartesia import Cartesia
from .schemas import FullScript
from loguru import logger

class VideoRenderer:
    def __init__(self, output_dir="temp/output"):
        self.output_dir = output_dir
        self.temp_audio_dir = "temp/audio"
        self.temp_video_dir = "temp/video"
        self.api_key = os.getenv("CARTESIA_API_KEY")
        self.voice_id = "a892d232-f705-40d7-bc8d-e368b295ec2a"  # Harian
        
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_audio_dir, exist_ok=True)
        os.makedirs(self.temp_video_dir, exist_ok=True)
        
        if self.api_key:
            self.client = Cartesia(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("CARTESIA_API_KEY not found. Video rendering will fail or use mocks.")

    async def render(self, visual_plan: List[Dict[str, Any]], script: FullScript) -> str:
        if not self.client:
            return "error: Cartesia API key missing"

        segment_files = []
        
        # 1. Generate audio and render individual video segments
        for i, segment in enumerate(script.segments):
            visual = next((v for v in visual_plan if v["segment_id"] == segment.segment_id), None)
            if not visual:
                continue

            audio_path = os.path.join(self.temp_audio_dir, f"{segment.segment_id}.wav")
            video_path = os.path.join(self.temp_video_dir, f"{segment.segment_id}.mp4")
            
            # Generate TTS using Cartesia Sonic
            logger.info(f"Generating Cartesia audio for segment {segment.segment_id}")
            try:
                # Cartesia bytes call is blocking, so we wrap it in an executor or just run it
                # For simplicity in this async env, we'll use the bytes generator
                data_iter = self.client.tts.bytes(
                    model_id="sonic-3",
                    transcript=segment.narration,
                    voice={"mode": "id", "id": self.voice_id},
                    output_format={"container": "wav", "sample_rate": 44100, "encoding": "pcm_f32le"},
                )
                
                with open(audio_path, "wb") as f:
                    for chunk in data_iter:
                        f.write(chunk)
            except Exception as e:
                logger.error(f"Cartesia TTS failed: {str(e)}")
                continue
            
            image_path = visual["image_path"]
            
            # FFmpeg Command
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", image_path,
                "-i", audio_path,
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-shortest",
                video_path
            ]
            
            logger.info(f"Rendering segment {segment.segment_id}")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            await process.communicate()
            
            if process.returncode == 0:
                segment_files.append(video_path)
            else:
                logger.error(f"FFmpeg failed for segment {segment.segment_id}")

        # 2. Concatenate all segments
        if not segment_files:
            return "error: No segments rendered"

        final_video_path = os.path.join(self.output_dir, "final_video.mp4")
        concat_list_path = os.path.join(self.temp_video_dir, "concat_list.txt")
        
        with open(concat_list_path, "w") as f:
            for sf in segment_files:
                abs_path = os.path.abspath(sf).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")

        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            final_video_path
        ]
        
        logger.info("Concatenating segments into final video")
        concat_process = await asyncio.create_subprocess_exec(
            *concat_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        await concat_process.communicate()
        
        if concat_process.returncode == 0:
            logger.info(f"Final video rendered at: {final_video_path}")
            return f"file:///{os.path.abspath(final_video_path).replace('\\', '/')}"
        else:
            return "error: concatenation failed"
