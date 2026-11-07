"""Comparación real del motor Skia (dos escenas, sin TTS ni render sustituto).

python -m tools.preview_cinematic_motion
Genera legacy.mp4, mejoras_optin.mp4 y fotogramas PNG verificables.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

from stickman.audio import SR, write_wav
from stickman.render import VideoRenderer
from stickman.schema import validate_script


def script(opt_in: bool):
    first = {
        "narration": "Nora ve algo y comienza a avanzar.",
        "background": "cielo",
        "camera": "follow" if opt_in else "static",
        "speaker": "nora",
        "characters": [{
            "id": "nora", "x": -0.7, "pose": "wave", "expression": "happy",
            "actions": [{"at": 0.0, "move_to": 0.65}, {"at": 0.40, "pose": "point"}],
            **({"movement_ease": "ease_in_out"} if opt_in else {}),
        }],
        "props": [{"type": "lightbulb", "x": 0.2, "at": 0.45}],
    }
    second = {
        "narration": "La misma Nora mantiene su posición al pasar de plano.",
        "background": "lavanda",
        "camera": "follow" if opt_in else "static",
        "transition": "fade_from_black" if opt_in else "cut",
        "speaker": "nora",
        "characters": [{
            "id": "nora", "x": -0.7, "pose": "think", "expression": "surprised",
            "actions": [{"at": 0.2, "move_to": -0.1}],
            **({"continue_from_previous": True, "movement_ease": "ease_in_out"}
               if opt_in else {}),
        }],
        "props": [{"type": "phone", "holder": "nora", "at": 0.20}],
    }
    raw = {"title": "Nora - continuidad y cámara", "cast": [{
        "id": "nora", "name": "Nora",
        "preset": {"hair": "ponytail", "color": "#2F6FB0"}
    }], "scenes": [first, second]}
    result, warnings = validate_script(raw)
    if warnings:
        raise ValueError(repr(warnings))
    return result


def main():
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg debe estar en PATH")
    out = Path("artifacts/comparacion-cinematica-02")
    out.mkdir(parents=True, exist_ok=True)
    fps, durs = 24, [3.0, 3.0]
    for name, enabled in (("legacy", False), ("mejoras_optin", True)):
        wav, mp4 = out / f"{name}.wav", out / f"{name}.mp4"
        write_wav(wav, np.zeros(int(SR * sum(durs)), dtype=np.float32))
        try:
            renderer = VideoRenderer(script(enabled), "16:9", durs,
                                     np.zeros(round(fps * sum(durs)), dtype=np.float32), [],
                                     fps=fps, render_scale=0.65)
            renderer.render(str(mp4), str(wav))
            for i, frame in enumerate((0, 25, 71, 72, 80, 104, 142)):
                renderer.snapshot(frame, str(out / f"{name}_{i}.png"))
        finally:
            wav.unlink(missing_ok=True)
        if not mp4.exists() or mp4.stat().st_size < 1000:
            raise RuntimeError("No se creó MP4 válido: " + str(mp4))
        print(f"{name}: {mp4} ({mp4.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
