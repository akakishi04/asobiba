"""Display-size helpers shared by image previews."""
from __future__ import annotations


def preview_subsample(
    image_width: int, image_height: int, viewport_width: int,
    viewport_height: int, maximum: int,
) -> int:
    """Integer downscale factor fitting an image into its available viewport.

    Tk PhotoImage uses integer subsampling. Small or still-unmapped viewports
    fall back to a conservative capped preview size.
    """
    safe_width = max(80, min(maximum, viewport_width if viewport_width >= 40 else maximum))
    safe_height = max(80, min(maximum, viewport_height if viewport_height >= 40 else maximum))
    return max(
        1,
        (image_width + safe_width - 1) // safe_width,
        (image_height + safe_height - 1) // safe_height,
    )
