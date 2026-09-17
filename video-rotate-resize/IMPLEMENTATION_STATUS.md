# AI restoration implementation status

Branch: `feat/video-ai-restoration`

Implemented:

- Existing FFmpeg rotate/resize path retained when AI mode is disabled.
- RVRT 1x deblur backend (GoPro and DVD pretrained tasks).
- SeedVR2 standalone backend through `comfyorg/comfyui_seedvr2` `inference_cli.py`.
- RVRT -> SeedVR2 cascade.
- Lossless PNG / FFV1 intermediates for AI stages.
- Original audio and metadata remuxed into the final MP4.
- NVENC/libx264 final encoding retained.
- Separate Python/repository configuration for RVRT and SeedVR2.
- Low-VRAM SeedVR2 defaults aimed at 16 GB class NVIDIA GPUs.
- Cancellation terminates child process trees on Windows.
- Unit tests cover command generation, config persistence, PNG normalization, and FFmpeg pipeline generation without loading AI weights.

Runtime validation still requires the local RVRT/SeedVR2 environments and model weights because those dependencies are intentionally external to this repository.
