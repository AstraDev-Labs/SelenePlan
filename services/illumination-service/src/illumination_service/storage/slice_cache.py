"""Slice caching for high-performance timeline scrubbing."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image


class SliceCache:
    """LRU / in-memory cache for rendered time slices and tiles."""

    def __init__(self, max_items: int = 500) -> None:
        self.max_items = max_items
        self._cache: dict[str, bytes] = {}
        self._keys: list[str] = []

    def get_slice_bytes(self, product_id: str, time_index: int) -> bytes | None:
        key = f"{product_id}:t{time_index}"
        return self._cache.get(key)

    def put_slice_bytes(self, product_id: str, time_index: int, data: bytes) -> None:
        key = f"{product_id}:t{time_index}"
        if key not in self._cache and len(self._keys) >= self.max_items:
            oldest = self._keys.pop(0)
            self._cache.pop(oldest, None)
        self._cache[key] = data
        if key in self._keys:
            self._keys.remove(key)
        self._keys.append(key)

    def render_slice_png(self, slice_mask: np.ndarray) -> bytes:
        """Render boolean lit mask to grayscale/palette PNG bytes."""
        # 255 for lit (sunlight), 0 for shadow
        img_arr = np.where(slice_mask, 255, 0).astype(np.uint8)
        img = Image.fromarray(img_arr, mode="L")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


default_slice_cache = SliceCache()
