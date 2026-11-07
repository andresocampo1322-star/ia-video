"""Comprobación de paleta manga sin confundirla con evaluación artística."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from studio_pro.quality import check_clip, measure_monochrome

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg requerido")


def test_monochrome_palette_detection(tmp_path):
    for color, low, high in (("gray", 0.95, 1.0), ("red", 0.0, 0.20)):
        video = tmp_path / f"{color}.mp4"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s=288x512:r=12",
            "-t", "1", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", str(video)], check=True, timeout=90)
        value = measure_monochrome(video)["monochrome_fraction"]
        assert low <= value <= high
        quality = check_clip(video, expected_seconds=1, style="manga_monochrome")
        has_color_warning = any("coloreados" in s for s in quality["warnings"])
        assert has_color_warning is (color == "red")
