"""Previsualización automática opcional con el renderizador original.

python -m tools.preview_auto_enhance
Archivos: classic.mp4, enhanced.mp4 y PNG de fotogramas de comparación.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

from stickman.audio import SR, write_wav
from stickman.enhance import enhance_script
from stickman.render import VideoRenderer
from stickman.schema import validate_script


def example():
    raw = {
        "title": "Ejemplo de mejora opcional",
        "cast": [{"id": "nora", "preset": {"hair": "ponytail", "color": "#2F6FB0"}}],
        "scenes": [
            {
                "narration": "Nora camina hacia su objetivo.",
                "background": "cielo", "camera": "static",
                "characters": [{"id": "nora", "x": -0.75, "pose": "wave",
                                "actions": [{"at": 0.0, "move_to": 0.65}]}],
                "props": [{"type": "lightbulb", "x": 0.8, "at": 0.4}]
            },
            {
                "narration": "Nora continúa desde donde terminó la escena anterior.",
                "background": "cielo", "camera": "static",
                "characters": [{"id": "nora", "x": -0.75, "pose": "point",
                                "actions": [{"at": 0.10, "move_to": 0.15}]}],
                "props": [{"type": "phone", "holder": "nora", "at": 0.4}]
            }
        ]
    }
    obj, warnings = validate_script(raw)
    if warnings:
        raise ValueError(str(warnings))
    return obj


def main():
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg debe estar en PATH")
    dest = Path("artifacts/comparacion-modo-automatico-03")
    dest.mkdir(parents=True, exist_ok=True)
    durations = [3.1, 3.1]
    fps = 24
    original = example()
    for label, s in (("classic", original), ("enhanced", enhance_script(original))):
        wav, mp4 = dest / f"{label}.wav", dest / f"{label}.mp4"
        write_wav(wav, np.zeros(round(SR * sum(durations)), np.float32))
        try:
            renderer = VideoRenderer(s, "16:9", durations,
                                     np.zeros(round(fps * sum(durations)), np.float32),
                                     [], fps=fps, render_scale=0.55)
            renderer.render(str(mp4), str(wav))
            for idx, frame in enumerate((0, 20, 48, 73, 83, 112, 145)):
                renderer.snapshot(frame, str(dest / f"{label}_{idx}.png"))
        finally:
            wav.unlink(missing_ok=True)
        if mp4.stat().st_size < 1000:
            raise RuntimeError("Archivo MP4 insuficiente: " + str(mp4))
        print(label, mp4, mp4.stat().st_size)


if __name__ == "__main__":
    main()
