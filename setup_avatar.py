#!/usr/bin/env python3
"""
setup_avatar.py — One-time avatar character setup script.

Run this once after placing your character JPG in resources/avatar/character_idle.jpg
It will:
  1. Validate the image exists and is readable
  2. Run the background-removal + circular-crop preprocessing
  3. Save the ready-to-use avatar PNG to temp/visuals/avatar/
  4. Print a preview of the avatar's final appearance in terminal (ASCII art)

Usage:
    python setup_avatar.py
    python setup_avatar.py --source path/to/my_character.jpg
    python setup_avatar.py --size 320  # change PiP window size (default: 280px)
"""

import os
import sys
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Teaching Monster avatar setup")
    parser.add_argument(
        "--source",
        default="resources/avatar/character_idle.jpg",
        help="Path to your character image (JPG or PNG)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=280,
        help="Diameter of the circular avatar window in pixels (default: 280)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        default=True,
        help="Open the output PNG for visual verification (default: true)",
    )
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"\n[ERROR] Character image not found: {source}")
        print(f"\n   Please copy your character JPG to:")
        print(f"   {source.absolute()}\n")
        sys.exit(1)

    print(f"\n[SETUP] Teaching Monster Avatar Setup")
    print(f"   Source  : {source}")
    print(f"   Size    : {args.size}px circular window")
    print()

    # Ensure output dir
    out_dir = Path("temp/visuals/avatar")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"avatar_circle_{args.size}.png"

    # Run preprocessing
    print("[...] Removing background and applying circular mask...")
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from modules.m6c_avatar_gen import _preprocess_character
        _preprocess_character(str(source), str(out_path), size=args.size)
        print(f"[OK] Avatar PNG saved -> {out_path}")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure you're running from the project root with the venv active.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        sys.exit(1)

    # Quick file size check
    size_kb = out_path.stat().st_size / 1024
    print(f"   File size: {size_kb:.1f} KB")

    # Preview
    if args.preview:
        try:
            from PIL import Image
            img = Image.open(out_path)
            print(f"   Dimensions: {img.size[0]}x{img.size[1]}px, mode={img.mode}")
            # Try to show the image
            img.show()
            print("   (Preview window opened)")
        except Exception:
            print("   (Install Pillow + image viewer to preview)")

    print()
    print("[DONE] Avatar ready! The character will appear in the bottom-right corner")
    print("   of every lesson video with a floating idle animation.")
    print()
    print("   To disable: set AVATAR_ENABLED=false in .env")
    print("   To change character: replace resources/avatar/character_idle.jpg")
    print()


if __name__ == "__main__":
    main()
