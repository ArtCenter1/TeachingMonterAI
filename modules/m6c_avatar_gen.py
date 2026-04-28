"""
M6C AvatarGen — Animated Professor Avatar PiP Compositor

Composites the Teaching Monster chibi professor character into the bottom-right
corner of lesson videos as a circular picture-in-picture (PiP) window.

Tier 1 (active): FFmpeg idle animation — gentle floating bob + slide-in reveal
  - Works with any character JPG/PNG
  - Handles white background removal via pillow (threshold mask)
  - Circular crop with subtle glowing border
  - Zero external API calls

Tier 2 (future): Replicate SadTalker lip-sync (enable via AVATAR_LIPSYNC=true)
  - Requires REPLICATE_API_KEY in .env
  - ~$0.14 per segment clip
"""

import os
import asyncio
import subprocess
import math
from typing import Optional
from loguru import logger


# ── Config ──────────────────────────────────────────────────────────────────

AVATAR_CHARACTER_PATH_ENV = "AVATAR_CHARACTER_PATH"
AVATAR_LIPSYNC_ENV        = "AVATAR_LIPSYNC"       # "true" to enable Replicate
REPLICATE_API_KEY_ENV     = "REPLICATE_API_KEY"

# Fallback character path (relative to project root)
DEFAULT_CHARACTER_PATH = "resources/avatar/character_idle.jpg"

# PiP window dimensions (pixels in the final video)
AVATAR_SIZE_PX = 200   # diameter for 720p landscape


def _ffmpeg_path() -> str:
    for candidate in ["ffmpeg", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        try:
            subprocess.run([candidate, "-version"], capture_output=True, check=True)
            return candidate
        except Exception:
            continue
    raise RuntimeError("FFmpeg not found.")


def _run_ffmpeg(args: list[str], label: str = ""):
    cmd = [_ffmpeg_path(), "-y"] + args
    logger.debug(f"[M6C] FFmpeg {label}: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"[M6C] FFmpeg {label} failed:\n{result.stderr[-2000:]}")
        raise RuntimeError(f"FFmpeg {label} failed: {result.stderr[-500:]}")
    return result


# ── Image preprocessing ─────────────────────────────────────────────────────

def _preprocess_character(source_path: str, output_path: str, size: int = AVATAR_SIZE_PX):
    """
    Convert character JPG → square PNG with:
      1. White/near-white background removed (pillow threshold mask)
      2. Character centered and fitted to square canvas
      3. Circular mask applied (anti-aliased)
      4. Glowing ring border added (teaching-brand gold/amber color)

    Returns the output PNG path.
    """
    from PIL import Image, ImageDraw, ImageFilter

    img = Image.open(source_path).convert("RGBA")

    # --- Step 1: Remove white background ---
    # Any pixel where R+G+B > 660 (out of 765) and all channels > 200 is background
    data = img.getdata()
    new_data = []
    for r, g, b, a in data:
        if r > 210 and g > 210 and b > 210:
            new_data.append((r, g, b, 0))  # transparent
        else:
            new_data.append((r, g, b, a))
    img.putdata(new_data)

    # --- Step 2: Auto-crop to content ---
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    # --- Step 3: Resize to fit in a square canvas (with padding) ---
    pad = int(size * 0.05)
    inner_size = size - 2 * pad
    img.thumbnail((inner_size, inner_size), Image.LANCZOS)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    paste_x = (size - img.width) // 2
    paste_y = (size - img.height) // 2
    canvas.paste(img, (paste_x, paste_y), img)

    # --- Step 4: Apply circular mask ---
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([0, 0, size - 1, size - 1], fill=255)

    # Smooth the mask edges slightly
    mask = mask.filter(ImageFilter.GaussianBlur(radius=1.5))

    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(canvas, mask=mask)

    # --- Step 5: Draw glowing amber ring border ---
    ring = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(ring)
    bw = 4  # border width
    # Outer glow (soft)
    for glow in range(4, 0, -1):
        alpha = int(180 * (glow / 4))
        ring_draw.ellipse(
            [bw - glow, bw - glow, size - bw + glow - 1, size - bw + glow - 1],
            outline=(255, 190, 50, alpha),
            width=1,
        )
    # Main border
    ring_draw.ellipse([bw, bw, size - bw - 1, size - bw - 1],
                      outline=(255, 190, 50, 230), width=bw - 1)

    output = Image.alpha_composite(output, ring)
    output.save(output_path, "PNG")
    logger.info(f"[M6C] Character preprocessed → {output_path}")
    return output_path


# ── Idle animation ──────────────────────────────────────────────────────────

def _create_idle_avatar_clip(
    character_png: str,
    duration: float,
    output_path: str,
    fps: int = 24,
) -> str:
    """
    Create an avatar video clip (RGBA/webm) with a gentle floating animation.

    The avatar will:
      - Float up and down with a 2.5s sinusoidal cycle
      - Have a smooth slide-in from below on the first 0.5s
      - Stay at bottom-right of a transparent canvas sized for overlay

    The output is a video with alpha channel (using libvpx-vp9 + yuva420p)
    OR a video without alpha (the overlay is handled in the main filter_complex).

    Returns output_path.
    """
    size = AVATAR_SIZE_PX

    # FFmpeg expression: sinusoidal float, amplitude 6px, period 2.5s
    # y_offset goes from 0 → -6 → 0 → +6 → 0 per cycle
    bob_amplitude = 6
    bob_period = 2.5

    # We build the avatar as an input image loop, then apply geq (pixel manipulation)
    # for the bob using overlay filter with a computed y offset.
    # Actually, simpler: use a single image input and compute the overlay position
    # dynamically in the compositor filter rather than pre-rendering a clip.
    # → We'll save the static PNG and compute bob in _build_avatar_ffmpeg_filter().

    # For this function, just validate the file exists; the real animation
    # is baked into the composite FFmpeg command in AvatarCompositor.
    if not os.path.exists(character_png):
        raise FileNotFoundError(f"Avatar PNG not found: {character_png}")

    return character_png  # Pass-through; motion baked at composite time


# ── Main compositor ─────────────────────────────────────────────────────────

class AvatarCompositor:
    """
    Composites the professor avatar onto a rendered segment video.
    Used by m7_renderer.py as the final overlay step.
    """

    def __init__(self):
        self._enabled = os.getenv("AVATAR_ENABLED", "true").lower() == "true"
        self._character_png: Optional[str] = None  # preprocessed PNG path
        self._source_path = (
            os.getenv(AVATAR_CHARACTER_PATH_ENV, DEFAULT_CHARACTER_PATH)
        )
        self._prep_dir = "temp/visuals/avatar"
        os.makedirs(self._prep_dir, exist_ok=True)

    def is_enabled(self) -> bool:
        return self._enabled and os.path.exists(self._source_path)

    def get_preprocessed_png(self) -> Optional[str]:
        """
        Lazily preprocess the character image on first call.
        Returns path to the circular avatar PNG, or None if unavailable.
        """
        if not self.is_enabled():
            return None

        if self._character_png and os.path.exists(self._character_png):
            return self._character_png

        out = os.path.join(self._prep_dir, f"avatar_circle_{AVATAR_SIZE_PX}.png")
        if os.path.exists(out):
            self._character_png = out
            return out

        try:
            self._character_png = _preprocess_character(self._source_path, out)
            return self._character_png
        except Exception as e:
            logger.warning(f"[M6C] Character preprocessing failed: {e} — avatar disabled")
            self._enabled = False
            return None

    def build_overlay_filter(
        self,
        video_width: int,
        video_height: int,
        input_index: int = 1,
        duration: float = 10.0,
    ) -> tuple[str, str]:
        """
        Returns (filter_complex_str, map_arg) for FFmpeg to composite the avatar.

        The avatar:
          - Slides in from below in the first 0.5s
          - Floats with sinusoidal bob (±6px, 2.5s period)
          - Sits in the bottom-right corner with a 20px margin
          - Has a subtle drop shadow (approximated with dark padded bg)

        Parameters:
            video_width, video_height  — frame size of the main video
            input_index                — which FFmpeg input index the avatar PNG is (0-based)
            duration                   — total segment duration in seconds

        Returns:
            filter_complex: string to pass as -filter_complex
            output_label:   the label of the final composited stream (e.g. "[vout]")
        """
        size = 200
        margin_x = 40
        margin_y = 40  # closer to bottom in landscape, but still safe
 
        # Target position (bottom-right corner, resting state)
        base_x = video_width - size - margin_x
        base_y = video_height - size - margin_y

        # Slide-in: avatar starts size+10 pixels BELOW the frame
        # and eases to base_y over 0.5s
        slide_expr = (
            f"if(lt(t,0.5),"
            f"  {base_y} + {size+10} * (1 - t/0.5),"   # ease in from below
            f"  {base_y} + {-6} * sin(2*PI*t/{2.5})"    # steady float
            f")"
        )

        # Shadow: slightly larger dark circle behind the avatar
        # We simulate this with a dark overlay at (base_x-3, y-3)
        shadow_x = base_x - 3
        shadow_y_expr = (
            f"if(lt(t,0.5),"
            f"  {base_y+3} + {size+10} * (1 - t/0.5),"
            f"  {base_y+3} + {-6} * sin(2*PI*t/{2.5})"
            f")"
        )

        # We need two overlays: shadow circle (drawn via color pad) then avatar
        # Since shadow requires a separate source, we'll use a simpler approach:
        # colorize the avatar's padding area to appear as shadow directly.
        # Result: just the avatar with glow border (the border IS the visual indicator)

        filter_complex = (
            f"[{input_index}:v] scale={size}:{size} [av];"
            f"[0:v][av] overlay=x={base_x}:y='{slide_expr}':shortest=1 [vout]"
        )

        return filter_complex, "[vout]"

    def composite_segment(
        self,
        segment_video_path: str,
        output_path: str,
        duration: float,
        video_width: int = 720,
        video_height: int = 1280,
    ) -> str:
        """
        Apply avatar PiP overlay to a rendered segment video.

        This is called from m7_renderer.py after each segment render.
        Returns output_path (same as input if avatar is disabled or fails).
        """
        avatar_png = self.get_preprocessed_png()
        if not avatar_png:
            return segment_video_path  # passthrough

        filter_complex, vout_label = self.build_overlay_filter(
            video_width, video_height, input_index=1, duration=duration
        )

        try:
            _run_ffmpeg(
                [
                    "-i", segment_video_path,   # input 0: segment video
                    "-loop", "1",
                    "-i", avatar_png,            # input 1: avatar PNG (looped)
                    "-t", str(duration),
                    "-filter_complex", filter_complex,
                    "-map", vout_label,
                    "-map", "0:a",               # keep original audio
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "28",
                    "-c:a", "copy",
                    "-movflags", "+faststart",
                    output_path,
                ],
                "avatar_overlay",
            )
            logger.info(f"[M6C] ✓ Avatar composited → {output_path}")
            return output_path
        except Exception as e:
            logger.warning(f"[M6C] Avatar overlay failed: {e} — returning original")
            return segment_video_path


# ── Singleton factory ────────────────────────────────────────────────────────

_compositor: Optional[AvatarCompositor] = None


def get_avatar_compositor() -> AvatarCompositor:
    global _compositor
    if _compositor is None:
        _compositor = AvatarCompositor()
    return _compositor
