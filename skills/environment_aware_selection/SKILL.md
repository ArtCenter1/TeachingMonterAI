---
name: environment_aware_selection
description: Guide for selecting binary paths (like FFmpeg) and assets across Windows host and Linux Docker environments.
---

# Environment-Aware Asset Selection

This skill ensures that AI agents correctly identify and use the appropriate binary paths when the application is running in a cross-platform environment (e.g., Windows development host vs. Linux Docker container).

## Guidelines

1. **Detect Platform**: Always check `os.name`.
   - `nt` = Windows
   - `posix` = Linux / macOS / Docker

2. **Prefer System Binaries in Containers**: In Docker, binaries like `ffmpeg` should be installed via `apt-get` and accessed via the system path (`"ffmpeg"`), NOT via bundled `.exe` files.

3. **Fallback Strategy**:
   - If on Windows (`nt`) AND a local `.exe` exists in `bin/`, use it for portability.
   - For all other cases, use the system command.

4. **Transparent Logging**:
   - Log the detected platform.
   - Log the final path chosen.
   - This helps diagnose "FileNotFoundError" or architecture mismatches (Exec format error) quickly.

## Implementation Example (Python)

```python
import os
from loguru import logger

def get_ffmpeg_path():
    is_windows = os.name == 'nt'
    local_exe = os.path.join(os.getcwd(), "bin", "ffmpeg.exe")
    
    if is_windows and os.path.exists(local_exe):
        logger.info(f"Using local Windows FFmpeg: {local_exe}")
        return local_exe
    else:
        logger.info(f"Using system FFmpeg (Platform: {os.name})")
        return "ffmpeg"
```
