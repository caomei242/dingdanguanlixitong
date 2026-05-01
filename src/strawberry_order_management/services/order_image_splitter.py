from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps


@dataclass(frozen=True)
class OrderImageChunk:
    index: int
    image_bytes: bytes
    bbox: tuple[int, int, int, int]
    confidence: float


class OrderImageSplitter:
    """Split obvious multi-order screenshots before sending them to OCR."""

    def __init__(
        self,
        *,
        min_chunks: int = 2,
        max_chunks: int = 10,
        min_chunk_height: int = 90,
        merge_gap: int = 30,
        padding: int = 10,
    ) -> None:
        self.min_chunks = min_chunks
        self.max_chunks = max_chunks
        self.min_chunk_height = min_chunk_height
        self.merge_gap = merge_gap
        self.padding = padding

    def split(self, image_bytes: bytes) -> list[OrderImageChunk]:
        try:
            image = ImageOps.exif_transpose(Image.open(BytesIO(image_bytes))).convert("RGB")
        except Exception:
            return []

        width, height = image.size
        if width < 600 or height < self.min_chunk_height * self.min_chunks:
            return []

        background = self._estimate_background(image)
        scores = self._row_content_scores(image, background)
        if not scores:
            return []

        max_score = max(scores)
        if max_score <= 0:
            return []
        threshold = max(0.004, min(0.18, max_score * 0.16))

        segments = self._merge_segments(self._content_segments(scores, threshold))
        segments = [
            (start, end)
            for start, end in segments
            if end - start >= self.min_chunk_height
        ]
        chunks = self._build_chunks(image, segments, max_score)
        if chunks:
            return chunks

        header_segments = self._header_band_segments(scores, max(0.45, max_score * 0.55))
        segments = self._segments_from_header_bands(header_segments, height)
        chunks = self._build_chunks(image, segments, max_score)
        if chunks:
            return chunks
        return []

    def _build_chunks(
        self,
        image: Image.Image,
        segments: list[tuple[int, int]],
        confidence_base: float,
    ) -> list[OrderImageChunk]:
        if len(segments) < self.min_chunks or len(segments) > self.max_chunks:
            return []

        width, height = image.size
        chunks: list[OrderImageChunk] = []
        for index, (start, end) in enumerate(segments, start=1):
            top = max(0, start - self.padding)
            bottom = min(height, end + self.padding)
            bbox = (0, top, width, bottom)
            cropped = image.crop(bbox)
            buffer = BytesIO()
            cropped.save(buffer, format="PNG")
            chunks.append(
                OrderImageChunk(
                    index=index,
                    image_bytes=buffer.getvalue(),
                    bbox=bbox,
                    confidence=round(min(0.95, max(0.6, confidence_base)), 2),
                )
            )
        return chunks

    @staticmethod
    def _estimate_background(image: Image.Image) -> tuple[int, int, int]:
        width, height = image.size
        points = [
            (0, 0),
            (width - 1, 0),
            (0, height - 1),
            (width - 1, height - 1),
        ]
        colors = [image.getpixel(point) for point in points]
        return tuple(sorted(channel)[len(channel) // 2] for channel in zip(*colors))

    @staticmethod
    def _row_content_scores(image: Image.Image, background: tuple[int, int, int]) -> list[float]:
        width, height = image.size
        pixels = image.load()
        step = max(1, width // 500)
        sample_count = max(1, len(range(0, width, step)))
        scores: list[float] = []
        for y in range(height):
            changed = 0
            for x in range(0, width, step):
                red, green, blue = pixels[x, y]
                if abs(red - background[0]) + abs(green - background[1]) + abs(blue - background[2]) > 24:
                    changed += 1
            scores.append(changed / sample_count)
        return OrderImageSplitter._smooth(scores)

    @staticmethod
    def _smooth(values: list[float], radius: int = 3) -> list[float]:
        smoothed: list[float] = []
        for index in range(len(values)):
            start = max(0, index - radius)
            end = min(len(values), index + radius + 1)
            smoothed.append(sum(values[start:end]) / (end - start))
        return smoothed

    @staticmethod
    def _content_segments(scores: list[float], threshold: float) -> list[tuple[int, int]]:
        segments: list[tuple[int, int]] = []
        start: int | None = None
        for index, score in enumerate(scores):
            if score >= threshold and start is None:
                start = index
            elif score < threshold and start is not None:
                segments.append((start, index))
                start = None
        if start is not None:
            segments.append((start, len(scores)))
        return segments

    def _merge_segments(self, segments: list[tuple[int, int]]) -> list[tuple[int, int]]:
        if not segments:
            return []
        merged = [segments[0]]
        for start, end in segments[1:]:
            previous_start, previous_end = merged[-1]
            if start - previous_end <= self.merge_gap:
                merged[-1] = (previous_start, end)
            else:
                merged.append((start, end))
        return merged

    def _header_band_segments(self, scores: list[float], threshold: float) -> list[tuple[int, int]]:
        bands = [
            (start, end)
            for start, end in self._content_segments(scores, threshold)
            if end - start >= 10
        ]
        return bands

    def _segments_from_header_bands(
        self,
        header_segments: list[tuple[int, int]],
        image_height: int,
    ) -> list[tuple[int, int]]:
        starts: list[int] = []
        for start, _end in header_segments:
            if starts and start - starts[-1] < self.min_chunk_height:
                continue
            starts.append(start)
        if len(starts) < self.min_chunks:
            return []

        segments: list[tuple[int, int]] = []
        for index, start in enumerate(starts):
            end = starts[index + 1] if index + 1 < len(starts) else image_height
            if end - start >= self.min_chunk_height:
                segments.append((start, end))
        return segments
