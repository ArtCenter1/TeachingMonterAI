import os
import asyncio
import subprocess
from typing import List, Dict, Any
from gtts import gTTS
from .schemas import FullScript
from loguru import logger

class VideoRenderer:
    def __init__(self, output_dir="temp/output"):
        self.output_dir = output_dir
        self.temp_audio_dir = "temp/audio"
        self.temp_video_dir = "temp/video"
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_audio_dir, exist_ok=True)
        os.makedirs(self.temp_video_dir, exist_ok=True)

    async def render(self, visual_plan: List[Dict[str, Any]], script: FullScript) -> str:
        segment_files = []
        
        # 1. Generate audio and render individual video segments
        for i, segment in enumerate(script.segments):
            # Find the corresponding visual plan entry
            visual = next((v for v in visual_plan if v["segment_id"] == segment.segment_id), None)
            if not visual:
                continue

            audio_path = os.path.join(self.temp_audio_dir, f"{segment.segment_id}.mp3")
            video_path = os.path.join(self.temp_video_dir, f"{segment.segment_id}.mp4")
            
            # Generate TTS
            logger.info(f"Generating audio for segment {segment.segment_id}")
            tts = gTTS(text=segment.narration, lang='en')
            tts.save(audio_path)
            
            # Use FFmpeg to combine image and audio
            # Note: We use the image_path from the visual plan
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
        final_video_path = os.path.join(self.output_dir, "final_video.mp4")
        concat_list_path = os.path.join(self.temp_video_dir, "concat_list.txt")
        
        with open(concat_list_path, "w") as f:
            for sf in segment_files:
                # Use absolute path and escape single quotes for FFmpeg
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
            logger.error("FFmpeg concatenation failed")
            return "error: rendering failed"
