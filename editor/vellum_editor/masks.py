"""Person masks with u2net_human_seg (the same model rembg uses), run with onnxruntime.

Used to put the hero title behind the person, for the cut-out sticker, the
white silhouette flash, and to score how big the person is in a clip.
Works offline: the model ships inside the app.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import numpy as np
from PIL import Image

from .paths import HUMAN_SEG_MODEL

_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


class PersonMasker:
    def __init__(self, model_path: Path = HUMAN_SEG_MODEL, threads: int | None = None):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads or max(1, (os.cpu_count() or 2) - 1)
        opts.log_severity_level = 3
        self.session = ort.InferenceSession(str(model_path), opts, providers=["CPUExecutionProvider"])
        self.input = self.session.get_inputs()[0].name
        self._lock = threading.Lock()

    def predict(self, rgb: np.ndarray | Image.Image) -> np.ndarray:
        """Person probability (0..1) at the image's own size."""
        im = rgb if isinstance(rgb, Image.Image) else Image.fromarray(rgb)
        w, h = im.size
        small = np.asarray(im.convert("RGB").resize((320, 320), Image.LANCZOS), np.float32)
        small = small / max(1.0, float(small.max()))
        x = ((small - _MEAN) / _STD).transpose(2, 0, 1)[None].astype(np.float32)
        with self._lock:  # onnxruntime sessions are thread-safe, but this keeps CPU use predictable
            out = self.session.run(None, {self.input: x})[0][0, 0]
        prob = np.clip(out, 0, 1)
        return np.asarray(Image.fromarray((prob * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR), np.float32) / 255.0


_shared: PersonMasker | None = None
_shared_lock = threading.Lock()


def available() -> bool:
    if os.environ.get("VELLUM_NO_MASKS") == "1":
        return False
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return HUMAN_SEG_MODEL.exists()


def get_masker() -> PersonMasker | None:
    """One shared model per process, or None if the model isn't installed."""
    global _shared
    if not available():
        return None
    with _shared_lock:
        if _shared is None:
            _shared = PersonMasker()
    return _shared


def person_stats(mask: np.ndarray, threshold: float = 0.5) -> tuple[float, float, float, tuple[int, int, int, int] | None]:
    """(area fraction, centre x 0..1, head-ish y 0..1, bbox) of the person in a mask."""
    on = mask > threshold
    area = float(on.mean())
    if area < 0.004:
        return 0.0, 0.5, 0.45, None
    ys, xs = np.nonzero(on)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    h, w = mask.shape
    cx = float(xs.mean()) / w
    # aim a bit above the middle of the body so heads stay in frame when cropping
    cy = (y0 + 0.35 * (y1 - y0)) / h
    return area, cx, cy, (x0, y0, x1, y1)


def smooth_masks(masks: list[np.ndarray]) -> list[np.ndarray]:
    """Average each mask with its neighbours so edges don't flicker frame to frame."""
    if len(masks) < 3:
        return masks
    out = []
    for i in range(len(masks)):
        a = masks[max(0, i - 1)]
        b = masks[i]
        c = masks[min(len(masks) - 1, i + 1)]
        out.append(0.25 * a + 0.5 * b + 0.25 * c)
    return out
