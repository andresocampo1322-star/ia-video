"""Verificaciones técnicas de videos reales, sin prometer juicio estético.

Decodifica fotogramas mediante FFmpeg; no necesita GPU, OpenCV ni NumPy.
Un buen puntaje técnico no garantiza animación de calidad cinematográfica.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path


def _run(command: list[str], *, seconds: int = 45) -> subprocess.CompletedProcess:
    p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=seconds)
    if p.returncode:
        raise RuntimeError((p.stderr or b"Error FFmpeg").decode("utf-8", "replace")[-1000:])
    return p


def probe_video(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file() or p.stat().st_size < 1000:
        raise FileNotFoundError(f"Video ausente o incompleto: {p}")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe debe estar instalado en PATH")
    res = _run([ffprobe, "-v", "error", "-show_entries",
                "format=duration:stream=width,height,codec_type,nb_frames,r_frame_rate",
                "-of", "json", str(p)])
    data = json.loads(res.stdout)
    video = next((s for s in data.get("streams", [])
                  if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("El archivo no contiene una pista de video")
    width, height = int(video["width"]), int(video["height"])
    duration = float(data.get("format", {}).get("duration", 0))
    if width < 64 or height < 64 or not math.isfinite(duration) or duration < 0.2:
        raise ValueError("Resolución o duración de video inválida")
    return {"width": width, "height": height, "duration": duration,
            "has_audio": any(x.get("codec_type") == "audio" for x in data["streams"]),
            "bytes": p.stat().st_size}


def measure_motion(path: str | Path, *, samples: int = 8) -> dict:
    """Medida aproximada de diferencias visuales entre fotogramas reducidos.

    No identifica movimiento anatómico correcto ni consistencia de personajes.
    No usa muestras aleatorias. Para videos con cámara fija detecta quietud.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg no está disponible en PATH")
    if not 2 <= samples <= 16:
        raise ValueError("samples fuera de rango")
    duration = probe_video(path)["duration"]
    # FPS temporal uniforme usando fps=, sin exigir que los clips tengan fps constante.
    rate = samples / max(duration, 0.01)
    raw = _run([ffmpeg, "-hide_banner", "-v", "error", "-i", str(path),
                "-vf", f"fps={rate:.8f},scale=64:36,format=gray",
                "-frames:v", str(samples), "-f", "rawvideo", "-"],
               seconds=90).stdout
    size = 64 * 36
    frames = [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)]
    if len(frames) < 2:
        return {"samples": len(frames), "motion_score": 0.0,
                "black_fraction": 0.0, "warnings": ["No se pudieron decodificar varias muestras"]}
    diffs = []
    black = []
    for frame in frames:
        black.append(sum(value < 16 for value in frame) / size)
    for a, b in zip(frames, frames[1:]):
        diffs.append(sum(abs(a[k] - b[k]) for k in range(size)) / (size * 255))
    score = round(sum(diffs) / len(diffs), 5)
    black_fraction = round(sum(black) / len(black), 4)
    warnings = []
    if score < 0.002:
        warnings.append("Movimiento visual muy bajo; revisar si es imagen estática")
    if black_fraction > 0.90:
        warnings.append("Más del 90 % de la imagen es casi negra")
    return {"samples": len(frames), "motion_score": score,
            "black_fraction": black_fraction, "warnings": warnings}


def measure_monochrome(path: str | Path, *, samples: int = 5) -> dict:
    """Fracción aproximada de píxeles sin saturación cromática.

    Valida la paleta, NO el nivel de detalle, identidad, anatomía ni estética.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg debe estar instalado")
    duration = probe_video(path)["duration"]
    rate = samples / max(duration, 0.01)
    raw = _run([ffmpeg, "-hide_banner", "-v", "error", "-i", str(path),
                "-vf", f"fps={rate:.8f},scale=64:36,format=rgb24",
                "-frames:v", str(samples), "-f", "rawvideo", "-"],
               seconds=90).stdout
    total = len(raw) // 3
    if total < 200:
        return {"monochrome_fraction": 0.0, "palette_samples": total}
    near_gray = 0
    for i in range(0, total * 3, 3):
        r, g, b = raw[i], raw[i + 1], raw[i + 2]
        if max(r, g, b) - min(r, g, b) <= 20:
            near_gray += 1
    return {"monochrome_fraction": round(near_gray / total, 4),
            "palette_samples": total}


def check_clip(path: str | Path, expected_seconds: float, *, target_ratio: str = "9:16",
               style: str | None = None) -> dict:
    info = probe_video(path)
    warnings = []
    planned = max(0.2, float(expected_seconds))
    if info["duration"] < planned * 0.70:
        warnings.append("El plano dura menos del 70 % del tiempo previsto")
    desired = {"9:16": 9 / 16, "16:9": 16 / 9, "1:1": 1.0}[target_ratio]
    actual = info["width"] / info["height"]
    if abs(actual - desired) / desired > 0.035:
        warnings.append("La relación de aspecto difiere del guion")
    sample = measure_motion(path)
    warnings.extend(sample.pop("warnings"))
    palette = {}
    if style == "manga_monochrome":
        palette = measure_monochrome(path)
        if palette["monochrome_fraction"] < 0.90:
            warnings.append(
                "El clip solicitado como manga monocromático contiene "
                "demasiados píxeles coloreados")
    return {**info, **sample, **palette, "expected_seconds": planned,
            "warnings": warnings, "technical_ok": len(warnings) == 0}
