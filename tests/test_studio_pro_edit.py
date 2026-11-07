"""Pruebas reales de montaje FFmpeg, sin modelos de IA ni claves."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from studio_pro.cli import main
from studio_pro.edit import assemble, clips_from_jobs

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="FFmpeg y FFprobe necesarios para los tests de montaje")


def sample(path: Path, color: str, size: str = "320x180") -> Path:
    cmd = [shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"color=c={color}:s={size}:r=24",
           "-t", "0.4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           str(path)]
    subprocess.run(cmd, check=True, capture_output=True)
    assert path.is_file()
    return path


def test_ffmpeg_assembly_creates_valid_video(tmp_path):
    a = sample(tmp_path / "first.mp4", "black")
    b = sample(tmp_path / "second.mp4", "white")
    final = assemble([a, b], tmp_path / "episode.mp4")
    assert final.stat().st_size > 1000
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(final)],
        text=True, capture_output=True, check=True)
    assert float(probe.stdout.strip()) >= 0.7


def test_assembler_never_overwrites_without_force(tmp_path):
    a = sample(tmp_path / "clip.mp4", "red")
    out = tmp_path / "output.mp4"
    assemble([a], out)
    with pytest.raises(FileExistsError):
        assemble([a], out)
    assert assemble([a], out, force=True) == out.resolve()


def test_assembler_reports_mismatched_resolution(tmp_path):
    a = sample(tmp_path / "clip1.mp4", "black")
    b = sample(tmp_path / "clip2.mp4", "white", "640x360")
    with pytest.raises(ValueError, match="resolución"):
        assemble([a, b], tmp_path / "fail.mp4")


def test_jobs_manifest_preserves_shot_order(tmp_path):
    a = sample(tmp_path / "a.mp4", "black")
    b = sample(tmp_path / "b.mp4", "white")
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps([
        {"shot": "shot_001", "status": "completed", "files": [str(a)]},
        {"shot": "shot_002", "status": "completed", "files": [str(b)]},
    ]))
    assert clips_from_jobs(path) == [a, b]
    assert main(["assemble", "--jobs", str(path),
                 "--out", str(tmp_path / "final.mp4")]) == 0
    assert (tmp_path / "final.mp4").is_file()


def test_jobs_manifest_rejects_incomplete_plan(tmp_path):
    path = tmp_path / "jobs.json"
    path.write_text('[{"shot":"shot_001","status":"queued","files":[]}]')
    with pytest.raises(ValueError, match="sin terminar"):
        clips_from_jobs(path)
