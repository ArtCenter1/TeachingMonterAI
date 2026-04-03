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
        # Set Voice ID (using a verified working default voice)
        self.voice_id = "cec7cae1-ac8b-4a59-9eac-ec48366f37ae"
        
        # Determine FFmpeg path
        local_ffmpeg = os.path.join(os.getcwd(), "bin", "ffmpeg.exe")
        if os.path.exists(local_ffmpeg):
            self.ffmpeg_path = local_ffmpeg
            logger.info(f"Using local FFmpeg: {self.ffmpeg_path}")
        else:
            self.ffmpeg_path = "ffmpeg"  # Fallback to system PATH
            logger.info("Using system FFmpeg")

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_audio_dir, exist_ok=True)
        os.makedirs(self.temp_video_dir, exist_ok=True)
        
        if self.api_key:
            self.client = Cartesia(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("CARTESIA_API_KEY not found. Video rendering will fail.")

    async def render(self, visual_plan: List[Dict[str, Any]], script: FullScript, run_id: str = "default") -> Dict[str, str]:
        if not self.client:
            return {"video": "error", "subtitles": "error"}

        segment_files = []
        all_timestamps = []
        global_offset = 0.0
        
        run_audio_dir = os.path.join(self.temp_audio_dir, run_id)
        run_video_dir = os.path.join(self.temp_video_dir, run_id)
        os.makedirs(run_audio_dir, exist_ok=True)
        os.makedirs(run_video_dir, exist_ok=True)
        
        for i, segment in enumerate(script.segments):
            visual = next((v for v in visual_plan if v["segment_id"] == segment.segment_id), None)
            if not visual:
                continue

            # Switch to raw PCM file to avoid WAV header issues with FFmpeg
            audio_path = os.path.join(run_audio_dir, f"{segment.segment_id}.raw")
            video_path = os.path.join(run_video_dir, f"{segment.segment_id}.mp4")
            
            logger.info(f"Generating audio for segment {segment.segment_id}")
            
            segment_audio_data = b""
            try:
                # Use WebSocket with robust Cartesia v3 approach
                with self.client.tts.websocket_connect() as connection:
                    ctx = connection.context(
                        model_id="sonic-english",
                        voice={"mode": "id", "id": self.voice_id},
                        output_format={"container": "raw", "encoding": "pcm_s16le", "sample_rate": 44100},
                    )

                    # Send with correct keyword arguments for v3
                    # Ensuring model_id and voice are passed if the SDK version requires them again
                    # but typically they are in connection.context()
                    ctx.send(
                        model_id="sonic-english",
                        voice={"mode": "id", "id": self.voice_id},
                        transcript=segment.narration,
                        continue_=False,
                        add_timestamps=True
                    )

                    # Check for receive() and iterate
                    # Robust check if 'receive' exists
                    if hasattr(ctx, "receive"):
                        for response in ctx.receive():
                            if response.type == "chunk":
                                if response.data:
                                    segment_audio_data += response.data
                            elif response.type == "timestamps":
                                if hasattr(response, "word_timestamps") and response.word_timestamps:
                                    ts_obj = response.word_timestamps
                                    words = getattr(ts_obj, "words", [])
                                    starts = getattr(ts_obj, "start", [])
                                    ends = getattr(ts_obj, "end", [])
                                    for word, start, end in zip(words, starts, ends):
                                        all_timestamps.append({
                                            "word": str(word),
                                            "start": float(start) + global_offset,
                                            "end": float(end) + global_offset
                                        })
                            elif response.type == "error":
                                logger.error(f"Cartesia error: {response.message}")
                    else:
                        # Fallback for SDK versions where ctx itself is an iterator
                        for response in ctx:
                            if hasattr(response, "data") and response.data:
                                segment_audio_data += response.data

                # Write raw PCM data
                if not segment_audio_data:
                    logger.warning(f"No audio for {segment.segment_id}, using silence")
                    segment_audio_data = b"\x00" * 88200 # 1s silence

                with open(audio_path, "wb") as f:
                    f.write(segment_audio_data)

            except Exception as e:
                logger.exception(f"Audio generation failed for {segment.segment_id}: {str(e)}")
                segment_audio_data = b"\x00" * 88200
                with open(audio_path, "wb") as f:
                    f.write(segment_audio_data)
            
            audio_duration = len(segment_audio_data) / (44100.0 * 2.0)
            image_path = visual["image_path"]
            
            # FFmpeg Command for segment - Using raw PCM options
            cmd = [
                self.ffmpeg_path, "-y",
                "-threads", "1",
                "-loop", "1", "-t", str(audio_duration), "-i", image_path,
                "-f", "s16le", "-ar", "44100", "-ac", "1", "-i", audio_path,
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-c:a", "aac",
                "-b:a", "192k",
                "-map", "0:v:0",
                "-map", "1:a:0",
                video_path
            ]
            
            logger.info(f"Rendering segment {segment.segment_id}")
            
            # Use asyncio.to_thread with subprocess.run for Windows compatibility
            def run_ffmpeg():
                return subprocess.run(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    check=False
                )

            result = await asyncio.to_thread(run_ffmpeg)
            stdout, stderr = result.stdout, result.stderr
            returncode = result.returncode
            
            if returncode == 0:
                segment_files.append(video_path)
                global_offset += audio_duration
            else:
                logger.error(f"FFmpeg failed for segment {segment.segment_id}: {stderr.decode() if stderr else 'unknown error'}")

        # Final Concatenation
        if not segment_files:
            return {"video": "error", "subtitles": "error"}

        final_filename = f"final_video_{run_id}.mp4"
        final_video_path = os.path.join(self.output_dir, final_filename)
        concat_list_path = os.path.join(run_video_dir, "concat_list.txt")
        
        with open(concat_list_path, "w") as f:
            for sf in segment_files:
                f.write(f"file '{os.path.abspath(sf).replace('\\', '/')}'\n")

        concat_cmd = [
            self.ffmpeg_path, "-y",
            "-f", "concat", "-safe", "0", "-i", concat_list_path,
            "-c", "copy",
            final_video_path
        ]
        
        logger.info(f"Concatenating all segments into {final_filename}")
        
        def run_concat():
            return subprocess.run(
                concat_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )

        concat_result = await asyncio.to_thread(run_concat)
        # We don't strictly need to wait for result.stdout if we don't log it
        
        # SRT Generation
        subtitle_filename = f"subtitles_{run_id}.srt"
        subtitle_path = os.path.join(self.output_dir, subtitle_filename)
        self._generate_srt(all_timestamps, subtitle_path)
        
        return {"video": final_filename, "subtitles": subtitle_filename}

    def _generate_srt(self, timestamps: List[Dict[str, Any]], output_path: str):
        def format_time(seconds: float) -> str:
            hrs = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

        with open(output_path, "w", encoding="utf-8") as f:
            block_size = 6
            for i in range(0, len(timestamps), block_size):
                chunk = timestamps[i : i + block_size]
                if not chunk: continue
                f.write(f"{i // block_size + 1}\n")
                f.write(f"{format_time(chunk[0]['start'])} --> {format_time(chunk[-1]['end'])}\n")
                f.write(f"{' '.join([c['word'] for c in chunk]).strip()}\n\n")
