import os
import asyncio
import subprocess
import wave
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
        # Check local bin/ folder first
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
            logger.warning("CARTESIA_API_KEY not found. Video rendering will fail or use mocks.")

    async def render(self, visual_plan: List[Dict[str, Any]], script: FullScript, run_id: str = "default") -> Dict[str, str]:
        if not self.client:
            return {"video": "error", "subtitles": "error"}

        segment_files = []
        all_timestamps = []
        global_offset = 0.0
        
        # Use run_id to segregate concurrent runs
        run_audio_dir = os.path.join(self.temp_audio_dir, run_id)
        run_video_dir = os.path.join(self.temp_video_dir, run_id)
        os.makedirs(run_audio_dir, exist_ok=True)
        os.makedirs(run_video_dir, exist_ok=True)
        
        # 1. Generate audio (with timestamps) and render individual video segments
        for i, segment in enumerate(script.segments):
            visual = next((v for v in visual_plan if v["segment_id"] == segment.segment_id), None)
            if not visual:
                continue

            audio_path = os.path.join(run_audio_dir, f"{segment.segment_id}.wav")
            video_path = os.path.join(run_video_dir, f"{segment.segment_id}.mp4")
            
            logger.info(f"Generating Cartesia WebSocket audio for segment {segment.segment_id}")
            
            # Using WebSocket with Cartesia SDK v3.x API
            segment_audio_data = b""
            try:
                # Use sonic-english for maximum stability and compatibility
                with self.client.tts.websocket_connect() as connection:
                    # Create a context with the required generation parameters
                    ctx = connection.context(
                        model_id="sonic-english",
                        voice={"mode": "id", "id": self.voice_id},
                        output_format={"container": "raw", "encoding": "pcm_s16le", "sample_rate": 44100},
                    )

                    # Send the narration transcript to the context
                    ctx.send(
                        transcript=segment.narration,
                        add_timestamps=True,
                    )

                    # Use ctx.receive() to iterate over responses (v3.x SDK)
                    for response in ctx.receive():
                        if not response:
                            continue

                        if response.type == "chunk":
                            if response.data:
                                segment_audio_data += response.data

                        elif response.type == "timestamps":
                            if hasattr(response, "word_timestamps") and response.word_timestamps:
                                ts_obj = response.word_timestamps
                                try:
                                    words = getattr(ts_obj, "words", [])
                                    starts = getattr(ts_obj, "start", [])
                                    ends = getattr(ts_obj, "end", [])
                                    for word, start, end in zip(words, starts, ends):
                                        all_timestamps.append({
                                            "word": str(word),
                                            "start": float(start) + global_offset,
                                            "end": float(end) + global_offset
                                        })
                                except Exception as e:
                                    logger.warning(f"Failed to parse timestamps: {str(e)}")

                        elif response.type == "error":
                            logger.error(f"Cartesia WebSocket error for {segment.segment_id}: {response.message}")
                            break

                # Verify we got audio data
                if not segment_audio_data:
                    logger.error(f"No audio data received for segment {segment.segment_id}, using silence fallback")
                    # Create 1 second of silence (44100 Hz, 16-bit mono PCM = 88200 bytes)
                    segment_audio_data = b"\x00" * 88200

                with wave.open(audio_path, "wb") as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)  # 16-bit
                    f.setframerate(44100)
                    f.writeframes(segment_audio_data)

            except Exception as e:
                logger.exception(f"Cartesia WebSocket failed for segment {segment.segment_id}: {str(e)}")
                # Create silence fallback on exception
                logger.warning(f"Falling back to silence for segment {segment.segment_id}")
                segment_audio_data = b"\x00" * 88200
                with wave.open(audio_path, "wb") as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(44100)
                    f.writeframes(segment_audio_data)
            
            audio_duration = len(segment_audio_data) / (44100.0 * 2.0)
            image_path = visual["image_path"]
            
            # FFmpeg Command for segment - Optimized for memory efficiency
            cmd = [
                self.ffmpeg_path, "-y",
                "-threads", "4",  # Limit threads to prevent "Cannot allocate memory"
                "-loop", "1", "-t", str(audio_duration), "-i", image_path,
                "-i", audio_path,
                "-vf", "scale=1280:-2,format=yuv420p",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                video_path
            ]
            
            logger.info(f"Rendering segment {segment.segment_id} with duration {audio_duration:.2f}s")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                segment_files.append(video_path)
                global_offset += audio_duration
            else:
                logger.error(f"FFmpeg failed for segment {segment.segment_id}")
                if stderr:
                    logger.error(f"FFmpeg stderr: {stderr.decode()}")

        # 2. Concatenate all segments
        if not segment_files:
            return {"video": "error", "subtitles": "error"}

        temp_video_filename = f"temp_concat_{run_id}.mp4"
        temp_video_path = os.path.join(run_video_dir, temp_video_filename)
        concat_list_path = os.path.join(run_video_dir, "concat_list.txt")
        
        with open(concat_list_path, "w") as f:
            for sf in segment_files:
                abs_path = os.path.abspath(sf).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")

        # Initial concatenation
        concat_cmd = [
            self.ffmpeg_path, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            temp_video_path
        ]
        
        logger.info(f"Concatenating segments for {run_id}")
        concat_process = await asyncio.create_subprocess_exec(
            *concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await concat_process.communicate()
        
        # 3. Mixing Background Music (Sidechain/Volume Ducking)
        final_filename = f"final_video_{run_id}.mp4"
        final_video_path = os.path.join(self.output_dir, final_filename)
        bg_music_path = os.path.join(os.getcwd(), "resources", "bg_music.mp3")
        
        if os.path.exists(bg_music_path):
            logger.info(f"Mixing background music for {run_id}")
            # Mix music at 10% volume, looped to match duration
            mix_cmd = [
                self.ffmpeg_path, "-y",
                "-i", temp_video_path,
                "-stream_loop", "-1", "-i", bg_music_path,
                "-filter_complex", "[0:a]volume=1.0[v];[1:a]volume=0.1[m];[v][m]amix=inputs=2:duration=first[out]",
                "-map", "0:v", "-map", "[out]",
                "-c:v", "copy", "-c:a", "aac", "-shortest",
                final_video_path
            ]
            mix_process = await asyncio.create_subprocess_exec(
                *mix_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            await mix_process.communicate()
        else:
            # Fallback if music download failed
            os.rename(temp_video_path, final_video_path)

        # 4. Generate SRT file
        subtitle_filename = f"subtitles_{run_id}.srt"
        subtitle_path = os.path.join(self.output_dir, subtitle_filename)
        self._generate_srt(all_timestamps, subtitle_path)
        
        logger.info(f"Final video and SRT rendered for {run_id}")
        return {"video": final_filename, "subtitles": subtitle_filename}

    def _generate_srt(self, timestamps: List[Dict[str, Any]], output_path: str):
        """Generates standard SRT subtitles from word-level timestamps."""
        def format_time(seconds: float) -> str:
            hrs = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"

        with open(output_path, "w", encoding="utf-8") as f:
            # Group words into blocks of ~5 for readability
            block_size = 6
            for i in range(0, len(timestamps), block_size):
                chunk = timestamps[i : i + block_size]
                if not chunk:
                    continue
                
                f.write(f"{i // block_size + 1}\n")
                f.write(f"{format_time(chunk[0]['start'])} --> {format_time(chunk[-1]['end'])}\n")
                words_text = " ".join([c["word"] for c in chunk])
                f.write(f"{words_text.strip()}\n\n")
