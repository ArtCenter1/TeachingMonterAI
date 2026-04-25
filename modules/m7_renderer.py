"""
M7 VideoRenderer — Pure FFmpeg subprocess implementation.

Why pure FFmpeg instead of MoviePy?
- MoviePy TextClip calls ImageMagick for EVERY FRAME → very slow (6+ min for 3 segments).
- FFmpeg's drawtext filter renders text at mux time, not per-frame → 10× faster.
- A 3-segment 720×1280 video now encodes in ~30–60 seconds instead of 6 minutes.

Architecture:
  _generate_audio()             → Cartesia TTS → .wav file per segment
  _source_visual_path()         → Pexels download or color fallback → local .mp4 file path
  _render_infographic_segment() → FFmpeg: Ken Burns zoom on static AI infographic PNG
  _render_segment()             → FFmpeg: B-roll trim/resize + drawtext caption
  AvatarCompositor              → overlays professor avatar PiP on every segment
  render()                      → concat segments + mix BGM → final .mp4
"""

import os
import asyncio
import subprocess
import random
import math
import time
from typing import List, Dict, Any, Optional
from loguru import logger

from .schemas import FullScript
from .pexels_client import PexelsClient
from .m6c_avatar_gen import get_avatar_compositor


# ── Cartesia Key Pool ───────────────────────────────────────────────────────

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
        self._exhausted: Dict[int, float] = {}  # index → quarantine_until timestamp
        logger.info(f"[CartesiaPool] Initialized with {len(self._keys)} key(s)")

    def get_key(self) -> Optional[str]:
        """Returns next healthy key using round-robin, skipping quarantined ones."""
        now = time.time()
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
        try:
            idx = self._keys.index(key)
            self._exhausted[idx] = time.time() + quarantine_sec
            logger.warning(f"[CartesiaPool] Key #{idx+1} quarantined for {quarantine_sec}s")
        except ValueError:
            pass


_cartesia_pool: Optional[CartesiaKeyPool] = None


def get_cartesia_pool() -> CartesiaKeyPool:
    global _cartesia_pool
    if _cartesia_pool is None:
        _cartesia_pool = CartesiaKeyPool()
    return _cartesia_pool


# ── FFmpeg helpers ──────────────────────────────────────────────────────────

def _ffmpeg_path() -> str:
    """Find ffmpeg binary."""
    for candidate in ["ffmpeg", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        try:
            subprocess.run([candidate, "-version"], capture_output=True, check=True)
            return candidate
        except Exception:
            continue
    raise RuntimeError("FFmpeg not found. Install ffmpeg in the container.")


def _run_ffmpeg(args: list[str], step_label: str = ""):
    """Run an ffmpeg command, logging on failure."""
    cmd = [_ffmpeg_path(), "-y"] + args  # -y = overwrite output without prompting
    logger.debug(f"[FFmpeg] {step_label}: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"[FFmpeg] {step_label} failed (rc={result.returncode}):\n{result.stderr[-2000:]}")
        raise RuntimeError(f"FFmpeg {step_label} failed: {result.stderr[-500:]}")
    return result


# ── Main Renderer ───────────────────────────────────────────────────────────

class VideoRenderer:
    # Target resolution — 720p vertical (fast to encode, still looks great)
    WIDTH = 720
    HEIGHT = 1280
    FPS = 24

    def __init__(self, output_dir="temp/output"):
        self.output_dir = output_dir
        self.temp_audio_dir = "temp/audio"
        self.temp_video_dir = "temp/video"
        self.assets_dir = "temp/assets"
        self.pexels = PexelsClient()
        self.voice_id = "cec7cae1-ac8b-4a59-9eac-ec48366f37ae"

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_audio_dir, exist_ok=True)
        os.makedirs(self.temp_video_dir, exist_ok=True)
        os.makedirs(self.assets_dir, exist_ok=True)

        self.cartesia_pool = get_cartesia_pool()
        if len(self.cartesia_pool._keys) == 0:
            logger.warning("No CARTESIA_API_KEY configured. Video rendering will fail.")

        # Avatar compositor (professor PiP overlay)
        self.avatar = get_avatar_compositor()
        if self.avatar.is_enabled():
            logger.info("M7: Professor avatar overlay ENABLED")
        else:
            logger.info("M7: Avatar overlay disabled (no character file found)")

    def _get_cartesia_client(self):
        from cartesia import Cartesia
        key = self.cartesia_pool.get_key()
        if not key:
            raise RuntimeError("All Cartesia API keys are exhausted.")
        return Cartesia(api_key=key), key

    async def render(
        self,
        visual_plan: List[Dict[str, Any]],
        script: FullScript,
        run_id: str = "default",
    ) -> Dict[str, str]:
        if len(self.cartesia_pool._keys) == 0:
            logger.error("M7: No Cartesia API key — cannot render video")
            return {"video": "error", "subtitles": "error"}

        run_audio_dir = os.path.join(self.temp_audio_dir, run_id)
        run_video_dir = os.path.join(self.temp_video_dir, run_id)
        os.makedirs(run_audio_dir, exist_ok=True)
        os.makedirs(run_video_dir, exist_ok=True)

        logger.info(f"M7: Starting FFmpeg rendering for run {run_id}")
        t0 = time.time()

        segment_paths: list[str] = []

        for i, segment in enumerate(script.segments):
            visual = next(
                (v for v in visual_plan if v["segment_id"] == segment.segment_id), None
            )
            if not visual:
                continue

            # 1. TTS audio
            try:
                audio_path = await self._generate_audio(segment, run_audio_dir)
            except Exception as e:
                logger.error(f"M7: Audio failed for segment {segment.segment_id}: {e}")
                continue

            # 2. Get audio duration (needed to size the video clip)
            duration = self._get_audio_duration(audio_path)
            if duration <= 0:
                logger.warning(f"M7: Zero duration audio for {segment.segment_id}, skipping")
                continue

            # 3. Render segment: AI infographic (Ken Burns) OR Pexels B-roll
            seg_raw = os.path.join(run_video_dir, f"seg_{i:02d}_raw.mp4")
            caption = self._truncate_caption(segment.narration, 80)
            visual_source = visual.get("visual_source", "pexels_broll")

            if visual_source == "gemini_infographic":
                infographic_path = visual.get("infographic_path")
                if infographic_path and os.path.exists(infographic_path):
                    logger.info(f"M7: Segment {i} → AI infographic")
                    self._render_infographic_segment(
                        infographic_path=infographic_path,
                        audio_path=audio_path,
                        duration=duration,
                        caption=caption,
                        visual=visual,
                        output_path=seg_raw,
                        step=i,
                    )
                else:
                    logger.warning(f"M7: Infographic missing for seg {i}, fallback to B-roll")
                    broll_path = self._source_visual_path(visual, run_video_dir, i)
                    self._render_segment(
                        broll_path=broll_path, audio_path=audio_path,
                        duration=duration, caption=caption,
                        visual=visual, output_path=seg_raw, step=i,
                    )
            else:
                broll_path = self._source_visual_path(visual, run_video_dir, i)
                self._render_segment(
                    broll_path=broll_path, audio_path=audio_path,
                    duration=duration, caption=caption,
                    visual=visual, output_path=seg_raw, step=i,
                )

            # 4. Composite professor avatar PiP overlay
            seg_out = os.path.join(run_video_dir, f"seg_{i:02d}.mp4")
            seg_out = self.avatar.composite_segment(
                segment_video_path=seg_raw,
                output_path=seg_out,
                duration=duration,
                video_width=self.WIDTH,
                video_height=self.HEIGHT,
            )

            segment_paths.append(seg_out)
            logger.info(f"M7: Segment {i} done ({duration:.1f}s) [{visual_source}]")

        if not segment_paths:
            logger.error("M7: No segments rendered — aborting")
            return {"video": "error", "subtitles": "error"}

        # 5. Concatenate all segments
        concat_path = os.path.join(run_video_dir, "concat.mp4")
        self._concat_segments(segment_paths, concat_path)
        logger.info(f"M7: Segments concatenated ({time.time() - t0:.1f}s elapsed)")

        # 6. Mix BGM
        output_filename = f"TeachingMonster_{run_id}.mp4"
        output_path = os.path.join(self.output_dir, output_filename)
        bgm_path = "resources/bg_music.mp3"

        logger.info(f"M7: Starting final export → {output_path}")
        try:
            if os.path.exists(bgm_path):
                self._mix_bgm(concat_path, bgm_path, output_path)
            else:
                # No BGM — just copy concat to output
                _run_ffmpeg(
                    ["-i", concat_path, "-c", "copy", output_path],
                    "copy_no_bgm",
                )
        except Exception as export_err:
            logger.error(f"M7: Final export failed: {export_err}")
            return {"video": "error", "subtitles": "error"}

        elapsed = time.time() - t0
        logger.success(f"M7: Export complete → {output_path} ({elapsed:.1f}s total)")
        return {"video": output_filename, "subtitles": "built-in"}

    # ── Internal helpers ────────────────────────────────────────────────────

    def _get_audio_duration(self, path: str) -> float:
        """Use ffprobe to get duration of an audio file in seconds."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                capture_output=True, text=True, check=True,
            )
            return float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"M7: Could not probe duration of {path}: {e}")
            return 30.0  # safe fallback

    def _truncate_caption(self, text: str, max_chars: int) -> str:
        text = text.replace("'", "\u2019").replace('"', '\\"').replace("\n", " ")
        if len(text) > max_chars:
            return text[:max_chars - 3] + "..."
        return text

    def _source_visual_path(
        self, visual: Dict[str, Any], run_video_dir: str, idx: int
    ) -> str:
        """
        Download a B-roll clip based on keywords. 
        Iterates through keywords until a match is found.
        """
        keywords = visual.get("pexels_keywords", [])
        if not isinstance(keywords, list):
            keywords = [str(keywords)]

        # Add some broad fallbacks if the specific ones fail
        search_candidates = keywords + ["educational visualization", "abstract science background", "learning"]

        for query in search_candidates:
            if not query or len(query) < 3: continue
            try:
                logger.debug(f"M7: Sourcing video for segment {idx} using query: '{query}'")
                results = self.pexels.search_videos(query)
                if results:
                    video_url = results[0].get("url", "")
                    if video_url:
                        path = self.pexels.download_video(video_url)
                        if path and os.path.exists(path):
                            logger.info(f"M7: Successfully sourced video for segment {idx} with '{query}'")
                            return path
            except Exception as e:
                logger.warning(f"M7: Sourcing failed for '{query}': {e}")

        # Fallback: generate a 90-second solid-color video placeholder
        color_path = os.path.join(run_video_dir, f"color_{idx}.mp4")
        _run_ffmpeg(
            [
                "-f", "lavfi",
                "-i", f"color=c=0x1a1a2e:size={self.WIDTH}x{self.HEIGHT}:rate={self.FPS}",
                "-t", "90",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
                color_path,
            ],
            f"color_fallback_{idx}",
        )
        return color_path

    def _build_drawtext(self, caption: str, duration: float, visual: Dict[str, Any]) -> str:
        """Build the drawtext + reveal filter string (shared by both render paths)."""
        H = self.HEIGHT
        safe_caption = caption.replace("'", "\u2019").replace(":", "\\:")
        fontsize = 52
        text_y = int(H * 0.72)

        drawtext = (
            f"drawtext=text='{safe_caption}'"
            f":fontsize={fontsize}"
            f":fontcolor=white"
            f":borderw=3:bordercolor=black"
            f":x=(w-text_w)/2"
            f":y={text_y}"
            f":line_spacing=8"
            f":fix_bounds=true"
        )

        elements = visual.get("elements", [])
        if visual.get("reveal_sequential") and elements:
            interval = duration / (len(elements) + 1)
            for j, elem in enumerate(elements):
                safe_elem = self._truncate_caption(elem, 40).replace("'", "\u2019").replace(":", "\\:")
                delay = interval * (j + 1)
                elem_y = int(H * 0.25) + j * 70
                drawtext += (
                    f",drawtext=text='- {safe_elem}'"
                    f":fontsize=42"
                    f":fontcolor=yellow"
                    f":borderw=2:bordercolor=black"
                    f":x=(w-text_w)/2"
                    f":y={elem_y}"
                    f":enable='gte(t,{delay})'"
                )
        return drawtext

    def _render_infographic_segment(
        self,
        infographic_path: str,
        audio_path: str,
        duration: float,
        caption: str,
        visual: Dict[str, Any],
        output_path: str,
        step: int,
    ):
        """
        Render a segment using a static AI-generated infographic PNG.

        - Infographic is 16:9 (1920x1080); video frame is portrait 720x1280.
        - Image is scaled to fill the width, centered vertically on a dark navy pad.
        - Ken Burns slow zoom-in (1.0 → ~1.08) adds natural motion to the still image.
        - Subtitle drawtext overlaid at the bottom as usual.
        """
        W, H = self.WIDTH, self.HEIGHT
        fps = self.FPS
        total_frames = max(int(duration * fps), 1)

        # Height of the infographic when scaled to fill WIDTH (16:9 ratio)
        infographic_h = int(W * 9 / 16)  # e.g. 720 * 9/16 = 405px
        infographic_y = (H - infographic_h) // 2  # center vertically in portrait frame

        # Ken Burns: gentle zoom-in, 0.0008 per frame (barely noticeable but adds life)
        zoom_speed = 0.0008
        max_zoom = min(1.0 + zoom_speed * total_frames, 1.12)  # cap at 12% zoom
        ken_burns = (
            f"zoompan="
            f"z='min(zoom+{zoom_speed},{max_zoom:.4f})':"
            f"d={total_frames}:"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':"
            f"s={W}x{infographic_h}"  # output size of zoompan = infographic_h slot
        )

        drawtext = self._build_drawtext(caption, duration, visual)

        # Full filter chain:
        # 1. Scale infographic to WIDTH (preserving 16:9 aspect)
        # 2. Pad to full portrait height with dark navy background
        # 3. Ken Burns zoom on the padded frame
        # 4. Subtitle drawtext on top
        video_filter = (
            f"scale={W}:{infographic_h}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:0:{infographic_y}:color=0x0a1628,"
            f"zoompan=z='min(zoom+{zoom_speed},{max_zoom:.4f})':d={total_frames}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H},"
            f"{drawtext}"
        )

        _run_ffmpeg(
            [
                "-loop", "1",               # loop the static image
                "-framerate", str(fps),
                "-i", infographic_path,      # input 0: AI infographic PNG
                "-i", audio_path,            # input 1: TTS audio
                "-t", str(duration),
                "-vf", video_filter,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "25",               # slightly better quality for crisp text
                "-c:a", "aac",
                "-b:a", "128k",
                "-pix_fmt", "yuv420p",      # required for zoompan filter compatibility
                "-shortest",
                "-movflags", "+faststart",
                output_path,
            ],
            f"render_infographic_{step}",
        )

    def _render_segment(
        self,
        broll_path: str,
        audio_path: str,
        duration: float,
        caption: str,
        visual: Dict[str, Any],
        output_path: str,
        step: int,
    ):
        """
        Render a segment from Pexels B-roll video:
          1. Loop/trim to match audio duration
          2. Scale+crop to portrait WIDTH×HEIGHT
          3. Burn subtitle via drawtext
          4. Mix narration audio
        """
        W, H = self.WIDTH, self.HEIGHT
        drawtext = self._build_drawtext(caption, duration, visual)

        scale_crop = (
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H}"
        )
        video_filter = f"{scale_crop},{drawtext}"

        _run_ffmpeg(
            [
                "-stream_loop", "-1",
                "-i", broll_path,
                "-i", audio_path,
                "-t", str(duration),
                "-vf", video_filter,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                "-movflags", "+faststart",
                output_path,
            ],
            f"render_seg_{step}",
        )

    def _concat_segments(self, segment_paths: list[str], output_path: str):
        """Concatenate segments using FFmpeg concat demuxer (fast, no re-encode)."""
        list_file = output_path + ".txt"
        with open(list_file, "w") as f:
            for p in segment_paths:
                f.write(f"file '{os.path.abspath(p)}'\n")
        _run_ffmpeg(
            [
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                output_path,
            ],
            "concat",
        )
        try:
            os.remove(list_file)
        except Exception:
            pass

    def _mix_bgm(self, video_path: str, bgm_path: str, output_path: str):
        """Mix a background music track at low volume under the narration."""
        # amix: input 0 = narration (full vol), input 1 = BGM (15% vol)
        _run_ffmpeg(
            [
                "-i", video_path,
                "-stream_loop", "-1",
                "-i", bgm_path,
                "-filter_complex",
                "[1:a]volume=0.15[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=3[aout]",
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                "-movflags", "+faststart",
                output_path,
            ],
            "mix_bgm",
        )

    async def _generate_audio(self, segment: Any, output_dir: str) -> str:
        """Generate TTS audio using Cartesia pool with key rotation on failure."""
        audio_path = os.path.join(output_dir, f"{segment.segment_id}.wav")
        if os.path.exists(audio_path):
            return audio_path

        logger.info(f"M7: Generating voice for segment {segment.segment_id}")

        last_error = None
        for attempt in range(len(self.cartesia_pool._keys) or 1):
            try:
                client, used_key = self._get_cartesia_client()
                data_iterator = client.tts.bytes(
                    model_id="sonic-english",
                    transcript=segment.narration,
                    voice={"mode": "id", "id": self.voice_id},
                    output_format={
                        "container": "wav",
                        "encoding": "pcm_s16le",
                        "sample_rate": 44100,
                    },
                )
                with open(audio_path, "wb") as f:
                    for chunk in data_iterator:
                        f.write(chunk)
                logger.success(f"M7: Audio generated for segment {segment.segment_id}")
                return audio_path

            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                if any(kw in err_str for kw in ["429", "rate limit", "quota", "402", "unauthorized", "403"]):
                    quarantine_sec = 300 if any(k in err_str for k in ["402", "quota"]) else 120
                    logger.warning(f"M7: Cartesia key error ({e}) — quarantining for {quarantine_sec}s")
                    self.cartesia_pool.report_error(used_key, quarantine_sec)
                else:
                    logger.error(f"M7: Cartesia TTS failed (non-quota): {e}")
                    break

        raise RuntimeError(f"All Cartesia TTS attempts failed. Last error: {last_error}")
