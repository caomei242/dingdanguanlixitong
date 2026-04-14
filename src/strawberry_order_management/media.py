from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image


def default_sku_image_cache_dir() -> Path:
    return Path.home() / ".config" / "strawberry-order-management" / "cache" / "sku-images"


def crop_sku_image_from_order_screenshot(
    image_bytes: bytes,
    *,
    order_id: str = "",
    output_dir: Path | None = None,
) -> str:
    target_dir = output_dir or default_sku_image_cache_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            working = image.convert("RGB")
            width, height = working.size
            crop_box = (
                0,
                max(int(height * 0.14), 0),
                max(int(width * 0.20), 1),
                max(int(height * 0.74), 1),
            )
            cropped = working.crop(crop_box)
            bbox = cropped.convert("L").point(lambda value: 255 if value < 245 else 0).getbbox()
            if bbox:
                cropped = cropped.crop(bbox)
            file_stem = order_id.strip() or datetime.now().strftime("%Y%m%d%H%M%S%f")
            output_path = target_dir / f"{file_stem}.png"
            cropped.save(output_path, format="PNG")
        return str(output_path)
    except Exception:
        return ""
