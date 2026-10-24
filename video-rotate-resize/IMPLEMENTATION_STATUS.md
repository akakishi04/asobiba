# AI restoration implementation status

Branch: `feat/video-ai-restoration`

Implemented:

- Existing FFmpeg rotate/resize path retained when AI mode is disabled.
- Drag & Drop input on the main window / input field through a local `tkinterdnd2` bootstrap.
- D&D dependency stored under git-ignored `.app_deps/`, with normal browse fallback if bootstrap fails.
- RVRT 1x deblur backend (GoPro and DVD pretrained tasks).
- SeedVR2 standalone backend through `comfyorg/comfyui_seedvr2` `inference_cli.py`.
- RVRT -> SeedVR2 cascade.
- One-click managed AI environment setup.
- Lossless PNG / FFV1 intermediates for AI stages.
- Original audio and metadata remuxed into the final MP4.
- NVENC/libx264 final encoding retained.
- Separate Python environments for RVRT and SeedVR2.
- Low-VRAM SeedVR2 defaults aimed at 16 GB class NVIDIA GPUs.
- Cancellation terminates child process trees on Windows.
- Unit tests cover command generation, config persistence, setup layout/version pins, launcher configuration, PNG normalization, and FFmpeg pipeline generation without loading AI weights.

Runtime validation still requires the target Windows GUI and local RVRT/SeedVR2 CUDA environments. D&D and real model inference are intentionally left as target-machine validation gates.
