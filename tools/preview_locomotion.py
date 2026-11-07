"""Genera comparaciones MP4 reales usando VideoRenderer, sin IA externa ni TTS.

Uso: python -m tools.preview_locomotion
Los resultados se guardan bajo artifacts/comparacion-animaciones-01/.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

from stickman.audio import SR, write_wav
from stickman.render import VideoRenderer
from stickman.schema import validate_script


def main() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("Se requiere ffmpeg instalado y disponible en PATH")
    output = Path("artifacts/comparacion-animaciones-01")
    output.mkdir(parents=True, exist_ok=True)
    duration, fps = 3.3, 24

    for gait in ("walk", "run", "sneak"):
        character = {
            "id": "personaje",
            "x": -0.80,
            "pose": "idle",
            "actions": [{"at": 0.0, "move_to": 0.80}],
        }
        if gait != "walk":
            character["gait"] = gait
        raw = {
            "title": "Comparación de locomoción - " + gait,
            "cast": [{"id": "personaje", "name": "Personaje de prueba"}],
            "scenes": [{
                "narration": "Comparación visual de movimiento.",
                "background": "cielo",
                "camera": "static",
                "characters": [character],
            }],
        }
        script, warnings = validate_script(raw)
        if warnings:
            raise ValueError("Guion de prueba produjo avisos: " + repr(warnings))
        wav = output / (gait + ".wav")
        mp4 = output / (gait + ".mp4")
        try:
            write_wav(wav, np.zeros(round(SR * duration), dtype=np.float32))
            renderer = VideoRenderer(
                script, "16:9", [duration],
                np.zeros(round(duration * fps), dtype=np.float32),
                [], fps=fps, render_scale=0.75,
            )
            renderer.render(str(mp4), str(wav))
        finally:
            wav.unlink(missing_ok=True)
        if not mp4.is_file() or mp4.stat().st_size < 1000:
            raise RuntimeError("No se generó MP4 válido: " + str(mp4))
        print(f"{gait}: {mp4} ({mp4.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
