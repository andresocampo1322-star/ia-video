"""Narración opcional a partir del motor Piper ORIGINAL de Stickman IA.

Usa la síntesis y el WAV original; no reemplaza voces ni simula sincronización
labial. Si la narración no cabe en el plano, informa en vez de cortarla.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path

from .core import Shot
from .quality import probe_video


def make_narration(shots: list[Shot], destination: str | Path, *,
                   language: str = "es", rate: float = 1.0) -> dict[str, Path]:
    """Sintetiza todas las narraciones en un lote con Piper y escribe WAV por plano."""
    if not 0.7 <= rate <= 1.6:
        raise ValueError("Velocidad de voz fuera de rango")
    directory = Path(destination)
    directory.mkdir(parents=True, exist_ok=True)
    names = {shot.id: directory / (shot.id + ".wav") for shot in shots}
    if all(p.is_file() and p.stat().st_size > 1000 for p in names.values()):
        return names
    try:
        from stickman.tts import synthesize
        from stickman.audio import write_wav
    except ImportError as e:
        raise RuntimeError("Faltan Piper/NumPy del motor Stickman original") from e
    voice_parts, engine = synthesize(
        [s.text for s in shots], lang=language, engine="piper",
        rate=rate, log=lambda message: print("[Piper]", message))
    if len(voice_parts) != len(shots):
        raise RuntimeError("Piper no devolvió una voz por escena")
    for shot, samples in zip(shots, voice_parts):
        write_wav(names[shot.id], samples)
    (directory / "voice_info.json").write_text(
        json.dumps({"engine": engine, "language": language,
                    "rate": rate, "files": [str(v) for v in names.values()]},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return names


def wave_seconds(wav: str | Path) -> float:
    with wave.open(str(wav), "rb") as f:
        return f.getnframes() / f.getframerate()


def attach_narration(clip: str | Path, narration: str | Path,
                     output: str | Path, *, force: bool = False) -> Path:
    """Mezcla narración con sonido del clip si existe; no trunca la locución."""
    vid = Path(clip)
    voice = Path(narration)
    if not voice.is_file():
        raise FileNotFoundError(voice)
    info = probe_video(vid)
    audio_seconds = wave_seconds(voice)
    if audio_seconds > info["duration"] + 0.15:
        raise ValueError(
            f"Locución ({audio_seconds:.1f}s) más larga que el clip "
            f"({info['duration']:.1f}s). Aumenta la duración del plano en el "
            "modelo generativo o divide esa escena; no se cortará la voz.")
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        raise FileExistsError(target)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg no instalado")
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error",
           "-y" if force else "-n",
           "-i", str(vid), "-i", str(voice), "-map", "0:v:0"]
    if info["has_audio"]:
        cmd += ["-filter_complex",
                "[0:a:0]volume=0.24[amb];[1:a:0]volume=1.0[voice];"
                "[amb][voice]amix=inputs=2:duration=longest:dropout_transition=1[out]",
                "-map", "[out]"]
    else:
        cmd += ["-map", "1:a:0", "-af", "apad"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-t", str(info["duration"]), "-movflags", "+faststart", str(target)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode or not target.is_file():
        target.unlink(missing_ok=True)
        raise RuntimeError("No se pudo añadir voz: " + result.stderr[-1500:])
    return target
