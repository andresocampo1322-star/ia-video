"""Montaje de la narración Piper con los clips: probado sin síntesis externa."""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from studio_pro.quality import probe_video
from studio_pro.voice import attach_narration, wave_seconds


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="ffmpeg required")
def test_narration_attaches_real_audio(tmp_path):
    clip = tmp_path / "clip.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=288x512:rate=12",
        "-t", "2", "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", str(clip)
    ], check=True, timeout=90)
    wav = tmp_path / "speech.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(bytes(24000 * 2))
    assert abs(wave_seconds(wav) - 1) < 0.01
    output = attach_narration(clip, wav, tmp_path / "with_voice.mp4")
    assert output.stat().st_size > 2000
    info = probe_video(output)
    assert info["has_audio"]
    assert info["duration"] >= 1.9
    with pytest.raises(FileExistsError):
        attach_narration(clip, wav, output)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="ffmpeg required")
def test_voice_is_not_silently_cut(tmp_path):
    clip = tmp_path / "clip.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=black:size=160x90:rate=12",
        "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)
    ], check=True, timeout=60)
    wav = tmp_path / "long.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(bytes(24000 * 2 * 3))
    with pytest.raises(ValueError, match="más larga"):
        attach_narration(clip, wav, tmp_path / "should_not_exist.mp4")
    assert not (tmp_path / "should_not_exist.mp4").exists()
