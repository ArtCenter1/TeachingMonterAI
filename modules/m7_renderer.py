import os
import asyncio
import subprocess
import random
from typing import List, Dict, Any, Optional
from loguru import logger

# Performance note: Moviepy is used for high-level composition.
# For production Docker images, ensure ImageMagick and FFmpeg are installed.
try:
    from moviepy.editor import (
        VideoFileClip, AudioFileClip, ImageClip, TextClip,
        CompositeVideoClip, concatenate_videoclips, ColorClip,
        CompositeAudioClip, vfx
    )
    # MoviePy afx for audio looping (replaces deprecated AudioFileClip.loop())
    import moviepy.audio.fx.all as afx
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    afx = None
    logger.warning("MoviePy not found. Rendering will be severely limited.")

from .schemas import FullScript
from .pexels_client import PexelsClient


def _parse_cartesia_pool() -> list[str]:
    """Parse CARTESIA_API_KEY_POOL (comma-separated) or fall back to single key."""
    pool_raw = os.getenv("CARTESIA_API_KEY_POOL", "").strip()
    if pool_raw:
        return [k.strip() for k in pool_raw.split(",") if k.strip()]
    single = os.getenv("CARTESIA_API_KEY", "").strip()
    return [single] if single else []


class CartesiaKeyPool:
    """Simple round-robin key rotator for Cartesia API keys."""

    def __init__(self):
        self._keys = _parse_cartesia_pool()
        self._index = 0
        self._exhausted: Dict[int, float] = {}  # index -> quarantine_until timestamp
        logger.info(f"[CartesiaPool] Initialized with {len(self._keys)} key(s)")

    def get_key(self) -> Optional[str]:
        """Returns next healthy key using round-robin, skipping quarantined ones."""
        now = asyncio.get_event_loop().time() if asyncio._get_running_loop() else __import__("time").time()
        total = len(self._keys)
        if total == 0:
            return None
        for _ in range(total):
            idx = self._index % total
            self._index = (self._index + 1) % total
            quarantine_until = self._exhausted.get(idx)
            if quarantine_until is None or now >= quarantine_until:
                if quarantine_until is not None:
                    del self._exhausted[idx]
                    logger.info(f"[CartesiaPool] Key #{idx+1} auto-recovered")
                return self._keys[idx]
        logger.error("[CartesiaPool] All Cartesia keys are exhausted!")
        return None

    def report_error(self, key: str, quarantine_sec: int = 120):
        """Quarantine a key after a rate-limit or auth error."""
        import time
        try:
            idx = self._keys.index(key)
            self._exhausted[idx] = time.time() + quarantine_sec
            logger.warning(f"[CartesiaPool] Key #{idx+1} quarantined for {quarantine_sec}s")
        except ValueError:
            pass


# Module-level shared Cartesia pool
_cartesia_pool: Optional[CartesiaKeyPool] = None


def get_cartesia_pool() -> CartesiaKeyPool:
    global _cartesia_pool
    if _cartesia_pool is None:
        _cartesia_pool = CartesiaKeyPool()
    return _cartesia_pool


class VideoRenderer:
    def __init__(self, output_dir="temp/output"):
        self.output_dir = output_dir
        self.temp_audio_dir = "temp/audio"
        self.temp_video_dir = "temp/video"
        self.assets_dir = "temp/assets"
        self.pexels = PexelsClient()
        self.voice_id = "cec7cae1-ac8b-4a59-9eac-ec48366f37ae"

        # Resolution standard
        self.width = 1080
        self.height = 1920  # Vertical format for social media/competition "Wow" factor

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_audio_dir, exist_ok=True)
        os.makedirs(self.temp_video_dir, exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)

        # Use shared pool — individual Cartesia clients created per key at call time
        self.cartesia_pool = get_cartesia_pool()
        if len(self.cartesia_pool._keys) == 0:
            logger.warning("No CARTESIA_API_KEY configured. Video rendering will fail.")

    def _get_cartesia_client(self):
        """Get a Cartesia client using the next healthy key from the pool."""
        from cartesia import Cartesia
        key = self.cartesia_pool.get_key()
        if not key:
            raise RuntimeError("All Cartesia API keys are exhausted.")
        return Cartesia(api_key=key), key

    async def render(self, visual_plan: List[Dict[str, Any]], script: FullScript, run_id: str = "default") -> Dict[str, str]:
        if not MOVIEPY_AVAILABLE:
            logger.error("M7: MoviePy not available — cannot render video")
            return {"video": "error", "subtitles": "error"}

        if len(self.cartesia_pool._keys) == 0:
            logger.error("M7: No Cartesia API key — cannot render video")
            return {"video": "error", "subtitles": "error"}

        segment_clips = []
        run_audio_dir = os.path.join(self.temp_audio_dir, run_id)
        os.makedirs(run_audio_dir, exist_ok=True)

        logger.info(f"M7: Starting visual rendering for run {run_id}")

        for i, segment in enumerate(script.segments):
            visual = next((v for v in visual_plan if v["segment_id"] == segment.segment_id), None)
            if not visual:
                continue

            # 1. Generate Narration Audio
            try:
                audio_path = await self._generate_audio(segment, run_audio_dir)
            except Exception as e:
                logger.error(f"M7: Audio generation failed for segment {segment.segment_id}: {e}")
                continue

            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration

            # 2. Source Visual (Video -> Image -> Slide)
            # FIX: _source_visual is NOT async (Pexels client uses sync requests lib)
            visual_clip = self._source_visual(visual, duration)
            visual_clip = visual_clip.set_audio(audio_clip)

            # 3. Add Subtitles (Karaoke-style)
            caption = segment.narration
            if len(caption) > 80:
                caption = caption[:77] + "..."

            txt_clip = TextClip(
                caption,
                fontsize=70,
                color='white',
                font='Arial-Bold',
                stroke_color='black',
                stroke_width=2,
                method='caption',
                size=(self.width * 0.8, None),
                align='Center'
            ).set_duration(duration).set_position(('center', self.height * 0.75))

            # Combine
            final_segment = CompositeVideoClip([visual_clip, txt_clip], size=(self.width, self.height))
            segment_clips.append(final_segment)

        if not segment_clips:
            logger.error("M7: No segments rendered — aborting video export")
            return {"video": "error", "subtitles": "error"}

        # 4. Concatenate and add BGM
        logger.info("M7: Concatenating segments and adding BGM...")
        final_video = concatenate_videoclips(segment_clips, method="compose")

        # Add BGM — safe fallback: skip if file missing or MoviePy version incompatible
        bgm_path = "resources/bg_music.mp3"
        if os.path.exists(bgm_path):
            try:
                bgm_clip = AudioFileClip(bgm_path).volumex(0.15)
                target_dur = final_video.duration
                # Use afx.audio_loop (modern API) — fallback to manual loop if unavailable
                if afx is not None and hasattr(afx, 'audio_loop'):
                    bgm = afx.audio_loop(bgm_clip, duration=target_dur)
                elif bgm_clip.duration < target_dur:
                    # Manual loop: repeat clip until long enough, then trim
                    import math
                    repeats = math.ceil(target_dur / bgm_clip.duration)
                    from moviepy.editor import concatenate_audioclips
                    bgm = concatenate_audioclips([bgm_clip] * repeats).subclip(0, target_dur)
                else:
                    bgm = bgm_clip.subclip(0, target_dur)
                if final_video.audio is not None:
                    final_audio = CompositeAudioClip([final_video.audio, bgm])
                else:
                    final_audio = bgm
                final_video = final_video.set_audio(final_audio)
                logger.info("M7: BGM added successfully")
            except Exception as bgm_err:
                logger.warning(f"M7: BGM failed ({bgm_err}) — continuing without background music")

        # 5. Export
        output_filename = f"TeachingMonster_{run_id}.mp4"
        output_path = os.path.join(self.output_dir, output_filename)

        final_video.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="ultrafast"
        )

        # Cleanup moviepy objects
        for clip in segment_clips:
            clip.close()
        final_video.close()

        return {"video": output_filename, "subtitles": "built-in"}

    async def _generate_audio(self, segment: Any, output_dir: str) -> str:
        """Generate TTS audio using Cartesia pool with key rotation on failure."""
        audio_path = os.path.join(output_dir, f"{segment.segment_id}.wav")
        if os.path.exists(audio_path):
            return audio_path

        logger.info(f"M7: Generating voice for segment {segment.segment_id}")

        last_error = None
        # Try each key in the pool (up to pool size attempts)
        for attempt in range(len(self.cartesia_pool._keys) or 1):
            try:
                client, used_key = self._get_cartesia_client()
                data_iterator = client.tts.bytes(
                    model_id="sonic-english",
                    transcript=segment.narration,
                    voice={"mode": "id", "id": self.voice_id},
                    output_format={"container": "wav", "encoding": "pcm_s16le", "sample_rate": 44100},
                )
                with open(audio_path, "wb") as f:
                    for chunk in data_iterator:
                        f.write(chunk)
                logger.success(f"M7: Audio generated for segment {segment.segment_id}")
                return audio_path

            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                # Quarantine key on rate limit or quota errors
                if any(kw in err_str for kw in ["429", "rate limit", "quota", "402", "unauthorized", "403"]):
                    quarantine_sec = 300 if any(k in err_str for k in ["402", "quota"]) else 120
                    logger.warning(f"M7: Cartesia key error ({e}) — quarantining for {quarantine_sec}s")
                    self.cartesia_pool.report_error(used_key, quarantine_sec)
                else:
                    # Non-quota error — don't rotate keys, just fail
                    logger.error(f"M7: Cartesia TTS failed (non-quota): {e}")
                    break

        raise RuntimeError(f"All Cartesia TTS attempts failed. Last error: {last_error}")

    def _source_visual(self, visual: Dict[str, Any], duration: float):
        """
        Source a visual clip for a segment.
        NOTE: This is SYNCHRONOUS — PexelsClient uses the requests library (not async).
        Do NOT use 'await' when calling this method.
        """
        # Build a clean search query string from keywords list
        keywords = visual.get("pexels_keywords", [])
        if isinstance(keywords, list):
            query = " ".join(keywords) if keywords else "education"
        else:
            query = str(keywords) if keywords else "education"

        # Try Video — search_videos() is synchronous
        try:
            results = self.pexels.search_videos(query)
            if results:
                # Pick first result and download it
                best = results[0]
                video_url = best.get("url", "")
                if video_url:
                    video_path = self.pexels.download_video(video_url)
                    if video_path and os.path.exists(video_path):
                        clip = VideoFileClip(video_path)
                        # Loop if video too short, crop if too long
                        if clip.duration < duration:
                            clip = clip.loop(duration=duration)
                        else:
                            start_t = random.uniform(0, max(0, clip.duration - duration))
                            clip = clip.subclip(start_t, start_t + duration)
                        return self._resize_to_fill(clip)
        except Exception as e:
            logger.warning(f"M7: Pexels video sourcing failed for '{query}': {e}")

        # Fallback to Slide (Static Image)
        image_path = visual.get("image_path")
        if image_path and os.path.exists(image_path):
            clip = ImageClip(image_path).set_duration(duration)
            # Add subtle zoom (Ken Burns effect)
            clip = clip.resize(lambda t: 1 + 0.05 * t / duration)
            return self._resize_to_fill(clip)

        # Ultimate Fallback: Solid color background
        logger.warning(f"M7: No visual found for segment — using color fallback")
        return ColorClip(size=(self.width, self.height), color=(0, 0, 100)).set_duration(duration)

    def _resize_to_fill(self, clip):
        """Scale to fill the 1080x1920 frame while maintaining aspect ratio."""
        w, h = clip.size
        target_ratio = self.width / self.height
        clip_ratio = w / h

        if clip_ratio > target_ratio:
            # Clip is wider than target — scale based on height
            new_h = self.height
            new_w = int(w * (self.height / h))
            clip = clip.resize(height=new_h)
            margin = (new_w - self.width) / 2
            clip = clip.crop(x1=margin, x2=new_w - margin)
        else:
            # Clip is taller than target
            new_w = self.width
            new_h = int(h * (self.width / w))
            clip = clip.resize(width=new_w)
            margin = (new_h - self.height) / 2
            clip = clip.crop(y1=margin, y2=new_h - margin)

        return clip.set_position("center")
