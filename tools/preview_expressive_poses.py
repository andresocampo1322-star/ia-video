"""Demostración MP4 de nuevas poses con interpolación del renderer original.

python -m tools.preview_expressive_poses
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

from stickman.audio import SR, write_wav
from stickman.render import VideoRenderer
from stickman.schema import validate_script

POSES = ("crouch", "cower", "stagger", "attack", "reach", "guard")


def main():
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg no instalado")
    dst = Path("artifacts/poses-expresivas-04")
    dst.mkdir(parents=True, exist_ok=True)
    scenes = []
    expressions = ("thinking", "surprised", "sad", "angry", "neutral", "thinking")
    for i, (pose, expression) in enumerate(zip(POSES, expressions)):
        scenes.append({
            "narration": "Demostración de " + pose,
            "background": "noche" if i % 2 else "cielo",
            "camera": "static",
            "characters": [{
                "id": "nora", "x": 0, "pose": "idle",
                "expression": expression,
                "actions": [{"at": 0.13, "pose": pose}],
            }],
            "keywords": [{"text": pose.upper(), "at": 0.68}],
        })
    script, warnings = validate_script({
        "title": "Biblioteca de poses ampliada",
        "cast": [{"id": "nora",
                  "preset": {"hair": "ponytail", "color": "#2F6FB0"}}],
        "scenes": scenes
    })
    if warnings:
        raise ValueError(str(warnings))
    durs = [2.0] * len(scenes)
    fps = 24
    wav, mp4 = dst / "poses.wav", dst / "poses_expanded.mp4"
    write_wav(wav, np.zeros(round(SR * sum(durs)), np.float32))
    try:
        renderer = VideoRenderer(script, "16:9", durs,
                                 np.zeros(round(fps * sum(durs)), np.float32),
                                 [], fps=fps, render_scale=0.60)
        renderer.render(str(mp4), str(wav))
        for i, pose in enumerate(POSES):
            renderer.snapshot(i * 48 + 29, str(dst / f"{i+1:02d}_{pose}.png"))
    finally:
        wav.unlink(missing_ok=True)
    if not mp4.is_file() or mp4.stat().st_size < 1000:
        raise RuntimeError("Fallo al renderizar")
    print("MP4", mp4, mp4.stat().st_size)


if __name__ == "__main__":
    main()
