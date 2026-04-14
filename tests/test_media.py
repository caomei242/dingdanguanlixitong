from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from strawberry_order_management.media import crop_sku_image_from_order_screenshot


def test_crop_sku_image_from_order_screenshot_writes_png(tmp_path: Path):
    image = Image.new("RGB", (600, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 50, 120, 170), fill="#4b8cff")

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    output_path = crop_sku_image_from_order_screenshot(
        buffer.getvalue(),
        order_id="6952003434324366473",
        output_dir=tmp_path,
    )

    assert output_path
    saved = Path(output_path)
    assert saved.exists()
    assert saved.suffix == ".png"
    with Image.open(saved) as cropped:
        assert cropped.width > 0
        assert cropped.height > 0
