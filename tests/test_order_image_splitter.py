from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

from strawberry_order_management.services.order_image_splitter import OrderImageSplitter


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _draw_order_card(draw: ImageDraw.ImageDraw, top: int, *, width: int = 1000) -> None:
    draw.rounded_rectangle((24, top, width - 24, top + 150), radius=8, fill="white", outline="#d8e2f2")
    draw.rectangle((24, top, width - 24, top + 34), fill="#f4f7fb")
    draw.text((54, top + 10), "订单编号 6925000000000000000 下单时间 2026-04-29 15:58:48", fill="#1f2f4f")
    draw.rectangle((62, top + 58, 104, top + 112), fill="#8fb4ff")
    draw.text((132, top + 58), "【明日达】27000 婴儿水", fill="#1f2f4f")
    draw.text((520, top + 58), "待发货", fill="#1f2f4f")
    draw.text((720, top + 58), "桃子 [8131] 17804472821 山东省潍坊市", fill="#1f2f4f")


def test_order_image_splitter_splits_three_order_cards() -> None:
    image = Image.new("RGB", (1000, 620), "#eef3fb")
    draw = ImageDraw.Draw(image)
    for top in (36, 228, 420):
        _draw_order_card(draw, top)

    chunks = OrderImageSplitter().split(_png_bytes(image))

    assert len(chunks) == 3
    assert [chunk.index for chunk in chunks] == [1, 2, 3]
    assert chunks[0].bbox[1] < 50
    assert chunks[1].bbox[1] > chunks[0].bbox[3]
    assert all(chunk.image_bytes.startswith(b"\x89PNG") for chunk in chunks)


def test_order_image_splitter_does_not_split_single_order_card() -> None:
    image = Image.new("RGB", (1000, 240), "#eef3fb")
    draw = ImageDraw.Draw(image)
    _draw_order_card(draw, 36)

    chunks = OrderImageSplitter().split(_png_bytes(image))

    assert chunks == []


def test_order_image_splitter_splits_tight_table_rows_by_header_bands() -> None:
    image = Image.new("RGB", (1200, 520), "white")
    draw = ImageDraw.Draw(image)
    for top in (20, 180, 340):
        draw.rectangle((0, top, 1200, top + 36), fill="#f3f5f8")
        draw.text((50, top + 10), "订单编号 6925000000000000000 下单时间 2026-04-29 15:58:48", fill="#1f2f4f")
        draw.rectangle((60, top + 62, 110, top + 118), fill="#8fb4ff")
        draw.text((140, top + 64), "【明日达】27000 婴儿水", fill="#1f2f4f")
        draw.text((620, top + 64), "待发货", fill="#1f2f4f")
        draw.text((820, top + 64), "桃子 [8131] 17804472821 山东省潍坊市", fill="#1f2f4f")

    chunks = OrderImageSplitter().split(_png_bytes(image))

    assert len(chunks) == 3
    assert [chunk.index for chunk in chunks] == [1, 2, 3]
