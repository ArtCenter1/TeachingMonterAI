import os
import asyncio
import subprocess
import random
import base64
from typing import List, Dict, Any
from cartesia import Cartesia
from .schemas import FullScript
from .pexels_client import PexelsClient
from loguru import logger

# Performance note: Moviepy is used for high-level composition.
# For production Docker images, ensure ImageMagick and FFmpeg are installed.
try:
    from moviepy.editor import (
        VideoFileClip, AudioFileClip, ImageClip, TextClip, 
        CompositeVideoClip, concatenate_videoclips, ColorClip,
        CompositeAudioClip, vfx
    )
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    logger.warning("MoviePy not found. Rendering will be severely limited.")

class VideoRenderer:
    def __init__(self, output_dir="temp/output"):
        self.output_dir = output_dir
        self.temp_audio_dir = "temp/audio"
        self.temp_video_dir = "temp/video"
        self.assets_dir = "temp/assets"
        self.pexels = PexelsClient()
        self.api_key = os.getenv("CARTESIA_API_KEY")
        self.voice_id = "cec7cae1-ac8b-4a59-9eac-ec48366f37ae"
        
        # Resolution standard
        self.width = 1080
        self.height = 1920 # Vertical format for social media/competition "Wow" factor

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_audio_dir, exist_ok=True)
        os.makedirs(self.temp_video_dir, exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)

        if self.api_key:
            self.client = Cartesia(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("CARTESIA_API_KEY not found. Video rendering will fail.")

    async def render(self, visual_plan: List[Dict[str, Any]], script: FullScript, run_id: str = "default") -> Dict[str, str]:
        if not self.client or not MOVIEPY_AVAILABLE:
            return {"video": "error", "subtitles": "error"}

        segment_clips = []
        run_audio_dir = os.path.join(self.temp_audio_dir, run_id)
        os.makedirs(run_audio_dir, exist_ok=True)

        logger.info(f"M7: Starting visual rendering for run {run_id}")

        for i, segment in enumerate(script.segments):
            visual = next((v for v in visual_plan if v["segment_id"] == segment.segment_id), None)
            if not visual: continue

            # 1. Generate Narration Audio
            audio_path = await self._generate_audio(segment, run_audio_dir)
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration

            # 2. Source Visual (Video -> Image -> Slide)
            visual_clip = await self._source_visual(visual, duration)
            visual_clip = visual_clip.set_audio(audio_clip)

            # 3. Add Subtitles (Karaoke-style)
            # For brevity in this iteration, we use simple centered text. 
            # In Phase 3 we'll add the word-level highlight.
            caption = segment.narration
            if len(caption) > 80:
                caption = caption[:77] + "..."
            
            # Subtitle overlay
            txt_clip = TextClip(
                caption,
                fontsize=70,
                color='white',
                font='Arial-Bold',
                stroke_color='black',
                stroke_width=2,
                method='caption',
                size=(self.width*0.8, None),
                align='Center'
            ).set_duration(duration).set_position(('center', self.height*0.75))

            # Combine
            final_segment = CompositeVideoClip([visual_clip, txt_clip], size=(self.width, self.height))
            segment_clips.append(final_segment)

        # 4. Concatenate and add BGM
        logger.info("M7: Concatenating segments and adding BGM...")
        final_video = concatenate_videoclips(segment_clips, method="compose")
        
        # Add BGM
        bgm_path = "resources/bg_music.mp3"
        if os.path.exists(bgm_path):
            bgm = AudioFileClip(bgm_path).volumex(0.15).loop(duration=final_video.duration)
            final_audio = CompositeAudioClip([final_video.audio, bgm])
            final_video = final_video.set_audio(final_audio)

        # 5. Export
        output_filename = f"TeachingMonster_{run_id}.mp4"
        output_path = os.path.join(self.output_dir, output_filename)
        
        # Use low-res/fast preset for competition speed
        final_video.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="ultrafast"
        )

        # Cleanup moviepy objects
        for clip in segment_clips: clip.close()
        final_video.close()

        return {"video": output_filename, "subtitles": "built-in"}

    async def _generate_audio(self, segment: Any, output_dir: str) -> str:
        audio_path = os.path.join(output_dir, f"{segment.segment_id}.wav")
        if os.path.exists(audio_path): return audio_path

        logger.info(f"M7: Generating voice for segment {segment.segment_id}")
        # Standard Cartesia sync call (simplifying for now, can be async)
        # Note: Using the v1/v2 style client matching current environment
        data = self.client.tts.bytes(
            model_id="sonic-english",
            transcript=segment.narration,
            voice_id=self.voice_id,
            output_format={"container": "wav", "encoding": "pcm_s16le", "sample_rate": 44100},
        )
        with open(audio_path, "wb") as f:
            f.write(data)
        return audio_path

    async def _source_visual(self, visual: Dict[str, Any], duration: float):
        keywords = visual.get("pexels_keywords", [])
        
        # Try Video
        video_url = await self.pexels.search_videos(keywords)
        if video_url:
            video_path = await self.pexels.download_asset(video_url, "video")
            if video_path:
                clip = VideoFileClip(video_path)
                # Loop if video too short, crop if too long
                if clip.duration < duration:
                    clip = clip.loop(duration=duration)
                else:
                    # Random start time for variety
                    start_t = random.uniform(0, max(0, clip.duration - duration))
                    clip = clip.subclip(start_t, start_t + duration)
                
                # Resize and Crop to fill Vertical
                return self._resize_to_fill(clip)

        # Fallback to Slide (Static)
        image_path = visual.get("image_path")
        if image_path and os.path.exists(image_path):
            clip = ImageClip(image_path).set_duration(duration)
            # Add subtle zoom (Ken Burns)
            clip = clip.resize(lambda t: 1 + 0.05 * t/duration)
            return self._resize_to_fill(clip)

        # Ultimate Fallback: Blue Screen
        return ColorClip(size=(self.width, self.height), color=(0, 0, 100)).set_duration(duration)

    def _resize_to_fill(self, clip):
        # Scale to fill the 1080x1920 frame while maintaining aspect ratio
        w, h = clip.size
        target_ratio = self.width / self.height
        clip_ratio = w / h
        
        if clip_ratio > target_ratio:
            # Clip is wider than target - scale based on height
            new_h = self.height
            new_w = int(w * (self.height / h))
            clip = clip.resize(height=new_h)
            # Center crop
            margin = (new_w - self.width) / 2
            clip = clip.crop(x1=margin, x2=new_w - margin)
        else:
            # Clip is taller than target (rare for landscape pexels)
            new_w = self.width
            new_h = int(h * (self.width / w))
            clip = clip.resize(width=new_w)
            # Center crop
            margin = (new_h - self.height) / 2
            clip = clip.crop(y1=margin, y2=new_h - margin)
            
        return clip.set_position("center")
