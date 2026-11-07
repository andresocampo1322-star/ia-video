"""Demostración de escenarios y atmósfera dentro del renderer original Skia.

python -m tools.preview_scenery
Genera dos MP4 comparables y fotogramas de cada escenario.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

from stickman.audio import SR, write_wav
from stickman.render import VideoRenderer
from stickman.schema import validate_script


def storyboard(detailed: bool):
    place1 = {"environment": "street", "atmosphere": "rain"} if detailed else {}
    place2 = {"environment": "supermarket", "atmosphere": "fog"} if detailed else {}
    raw = {
        "title": "Nora - de la calle al supermercado",
        "cast": [
            {"id": "nora", "name": "Nora", "preset": {"hair": "ponytail", "color": "#2F6FB0"}},
            {"id": "guardia", "name": "Guardia", "preset": {"hair": "short", "accessory": "cap", "color": "#2E8B6A"}},
            {"id": "infectado", "name": "Infectado", "preset": {"hair": "spiky", "color": "#8C704D"}},
        ],
        "scenes": [
            {"narration": "Nora camina entre las tiendas bajo la lluvia.",
             "background": "noche", "camera": "pan_right",
             **place1,
             "characters": [
                 {"id": "nora", "x": -0.65, "pose": "idle",
                  "movement_ease": "ease_in_out",
                  "actions": [{"at": 0.0, "move_to": 0.55},
                              {"at": 0.55, "pose": "guard", "expression": "surprised"}]},
                 {"id": "guardia", "x": 0.72, "pose": "wave"}],
             "keywords": [{"text": "LA CALLE", "at": 0.12, "until": 0.42}]},
            {"narration": "Dentro del supermercado, alguien se tambalea hacia Nora.",
             "background": "noche", "camera": "zoom_in",
             **place2,
             "characters": [
                 {"id": "nora", "x": -0.44, "pose": "cower", "expression": "surprised"},
                 {"id": "infectado", "x": 0.65, "pose": "stagger", "expression": "angry",
                  "actions": [{"at": 0.12, "move_to": 0.15}, {"at": 0.74, "pose": "attack"}]}],
             "keywords": [{"text": "NO TE MUEVAS", "at": 0.55}]},
        ],
    }
    script, warnings = validate_script(raw)
    if warnings:
        raise ValueError(repr(warnings))
    return script


def main():
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("Falta ffmpeg")
    output = Path("artifacts/escenarios-vectoriales-05")
    output.mkdir(parents=True, exist_ok=True)
    fps, durations = 24, [3.8, 3.8]
    for label, enabled in (("original", False), ("escenarios_lluvia", True)):
        wav, mp4 = output / f"{label}.wav", output / f"{label}.mp4"
        write_wav(wav, np.zeros(round(SR * sum(durations)), np.float32))
        try:
            render = VideoRenderer(storyboard(enabled), "16:9", durations,
                                   np.zeros(round(fps * sum(durations)), np.float32), [],
                                   fps=fps, render_scale=0.60)
            render.render(str(mp4), str(wav))
            for i, frame in enumerate((5, 36, 77, 95, 128, 167)):
                render.snapshot(frame, str(output / f"{label}_{i}.png"))
        finally:
            wav.unlink(missing_ok=True)
        if not mp4.exists() or mp4.stat().st_size < 1000:
            raise RuntimeError("No se creó video " + str(mp4))
        print(label, mp4, mp4.stat().st_size)


if __name__ == "__main__":
    main()
