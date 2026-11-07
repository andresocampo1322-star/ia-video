"""Montaje básico de clips de modelos generativos mediante FFmpeg real.

Preserva orden y pistas de audio compatibles. No sintetiza voces ni lipsync.
Nunca reescribe el renderizador original de Stickman IA.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

EXTENSIONS = frozenset((".mp4", ".mov", ".mkv", ".webm"))


def _tool(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise RuntimeError(f"{name} no está disponible en PATH")
    return executable


def _probe(path: Path) -> dict:
    process = subprocess.run(
        [_tool("ffprobe"), "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height", "-of", "json", str(path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30, check=True)
    streams = json.loads(process.stdout).get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audios = [s for s in streams if s.get("codec_type") == "audio"]
    if len(videos) != 1:
        raise ValueError(f"Se requiere exactamente una pista de video: {path}")
    return {"width": videos[0]["width"], "height": videos[0]["height"],
            "has_audio": bool(audios)}


def clips_from_jobs(path: str | Path) -> list[Path]:
    """Lee el manifiesto de render-project --submit --wait, preservando orden."""
    manifest = Path(path)
    records = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError("El manifiesto jobs.json está vacío")
    selected = []
    for entry in records:
        if entry.get("status") != "completed":
            raise ValueError(f"Plano sin terminar: {entry.get('shot')}")
        videos = [Path(f) for f in entry.get("files", [])
                  if Path(f).suffix.lower() in EXTENSIONS]
        if len(videos) != 1:
            raise ValueError(f"Plano {entry.get('shot')}: esperado un solo archivo de video")
        selected.append(videos[0])
    return selected


def assemble(clips: list[str | Path], output: str | Path, *, force: bool = False) -> Path:
    """Compone clips compatibles sin inventar duración/imagen/voz.

    Se rechazan resoluciones mezcladas o mezcla de archivos con/sin audio para
    evitar un MP4 aparentemente correcto pero defectuoso.
    """
    if not clips:
        raise ValueError("No se han proporcionado clips")
    files = [Path(f).resolve() for f in clips]
    for f in files:
        if not f.is_file() or f.stat().st_size == 0:
            raise FileNotFoundError(f"Falta el clip: {f}")
        if f.suffix.lower() not in EXTENSIONS:
            raise ValueError(f"Formato de video no admitido: {f.suffix}")
    properties = [_probe(f) for f in files]
    first = properties[0]
    for f, p in zip(files[1:], properties[1:]):
        if p["width"] != first["width"] or p["height"] != first["height"]:
            raise ValueError(f"Los clips necesitan la misma resolución: {f.name}")
        if p["has_audio"] != first["has_audio"]:
            raise ValueError("Todos los clips deben tener audio o ninguno")
    target = Path(output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        raise FileExistsError(f"El video final ya existe: {target}")
    with tempfile.TemporaryDirectory(prefix="ia_video_concat_") as folder:
        listing = Path(folder) / "clips.txt"
        # La lista concat de FFmpeg usa comillas simples; los nombres no son comandos.
        escaped = []
        for f in files:
            path_text = f.as_posix().replace("'", "'\\''")
            escaped.append("file '" + path_text + "'")
        listing.write_text("\n".join(escaped) + "\n", encoding="utf-8")
        command = [
            _tool("ffmpeg"), "-hide_banner", "-loglevel", "error",
            "-y" if force else "-n", "-f", "concat", "-safe", "0",
            "-i", str(listing), "-c:v", "libx264", "-preset", "medium",
            "-crf", "19", "-pix_fmt", "yuv420p",
        ]
        if first["has_audio"]:
            command += ["-c:a", "aac", "-b:a", "192k"]
        else:
            command += ["-an"]
        command += ["-movflags", "+faststart", str(target)]
        p = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        if p.returncode:
            target.unlink(missing_ok=True)
            raise RuntimeError("FFmpeg no pudo montar el episodio: " + p.stderr[-1500:])
    if not target.is_file() or target.stat().st_size < 1000:
        raise RuntimeError("La exportación terminó sin un MP4 utilizable")
    return target
