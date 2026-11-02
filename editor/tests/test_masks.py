"""The person-mask model (skipped when the model file isn't downloaded)."""
import os

import numpy as np
import pytest

from vellum_editor import masks
from vellum_editor.paths import HUMAN_SEG_MODEL

pytestmark = pytest.mark.skipif(not HUMAN_SEG_MODEL.exists(), reason="u2net_human_seg.onnx not downloaded")


def test_model_runs_and_finds_nobody_in_a_test_pattern(monkeypatch):
    monkeypatch.delenv("VELLUM_NO_MASKS", raising=False)
    masker = masks.PersonMasker()
    yy, xx = np.mgrid[0:180, 0:320]
    img = np.stack([(xx * 0.8) % 255, (yy * 1.4) % 255, np.full_like(xx, 90)], -1).astype(np.uint8)
    m = masker.predict(img)
    assert m.shape == (180, 320) and 0 <= m.min() and m.max() <= 1
    area, *_ = masks.person_stats(m)
    assert area < 0.05


def test_mask_smoothing_keeps_shape():
    ms = [np.full((10, 10), v, np.float32) for v in (0.0, 1.0, 0.0, 1.0)]
    out = masks.smooth_masks(ms)
    assert len(out) == 4 and all(o.shape == (10, 10) for o in out)
