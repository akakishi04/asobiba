# PR notes

This branch extends the existing Windows video utility with optional AI restoration while preserving the FFmpeg-only workflow.

Primary runtime entrypoint: `app_ai.py` (also launched by `run.bat`).

AI modes:

1. RVRT
2. SeedVR2
3. RVRT -> SeedVR2

The AI repositories, Python environments, and weights remain external and are configured locally through the GUI.
