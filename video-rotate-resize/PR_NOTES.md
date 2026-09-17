# PR notes

This branch extends the existing Windows video utility with optional AI restoration while preserving the FFmpeg-only workflow.

Primary runtime entrypoint: `launcher.py` (launched by `run.bat`). It bootstraps the local Drag & Drop dependency into `.app_deps/` and then starts `app_ai.py`.

AI modes:

1. RVRT
2. SeedVR2
3. RVRT -> SeedVR2

Input videos can be selected with the existing browse dialog or dropped onto the main window / input field.

The AI repositories, Python environments, model weights, GUI bootstrap dependencies and local settings remain external or git-ignored.
