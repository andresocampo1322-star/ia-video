"""Producción opcional real: libreto -> referencias -> planos -> video -> MP4.

Usa workflows de imagen y video exportados de ComfyUI y sus modelos instalados.
Sin GPU/servidor no finge producir clips: el modo seguro valida, planifica y sale.
La ruta de render Stickman IA permanece totalmente independiente.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .comfy import (ComfyClient, bind_workflow, load_api_workflow, load_bindings,
                    local_url)
from .core import Character, Project, Shot, load_cast, make_project
from .edit import EXTENSIONS, assemble
from .ollama import interpret_with_ollama
from .quality import check_clip


IMAGE_EXTS = frozenset((".png", ".jpg", ".jpeg", ".webp"))
VIDEO_EXTS = EXTENSIONS


@dataclass(frozen=True)
class Stage:
    name: str
    workflow: dict
    bindings: dict


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _stage(root: Path, data: dict, key: str, *, required: bool = True) -> Stage | None:
    value = data.get(key)
    if value is None:
        if required:
            raise ValueError(f"Configuración incompleta: falta '{key}'")
        return None
    if not isinstance(value, dict) or not value.get("workflow") or not value.get("bindings"):
        raise ValueError(f"{key}: se necesitan workflow y bindings")
    path_w = (root / str(value["workflow"])).resolve()
    path_b = (root / str(value["bindings"])).resolve()
    return Stage(key, load_api_workflow(path_w), load_bindings(path_b))


def _fingerprint(paths: list[Path], options: dict) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(options, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    for path in paths:
        digest.update(str(path.resolve()).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _single_file(files: list[Path], extensions: frozenset[str], stage: str) -> Path:
    matches = [p for p in files if p.suffix.lower() in extensions and p.is_file()]
    if len(matches) != 1:
        raise RuntimeError(
            f"{stage}: se esperaba UN archivo de {sorted(extensions)}, "
            f"pero se obtuvieron {len(matches)}. Revisa el nodo SaveImage/SaveVideo.")
    return matches[0]


def _reference_path(character: Character, cast_file: Path | None) -> Path | None:
    if not character.reference_image:
        return None
    image = Path(character.reference_image)
    if not image.is_absolute():
        if cast_file is None:
            raise ValueError(f"Referencia relativa sin archivo de reparto: {character.name}")
        image = cast_file.parent / image
    if not image.is_file():
        raise FileNotFoundError(f"No se encuentra referencia de {character.name}: {image}")
    if image.suffix.lower() not in IMAGE_EXTS:
        raise ValueError(f"Imagen inválida para {character.name}: {image}")
    return image.resolve()


def _character_shot(char: Character, style_prompt: str) -> Shot:
    prompt = (
        f"CHARACTER DESIGN REFERENCE SHEET, single character only: {char.anchor()}. "
        "Full body and close-up of the SAME identity, consistent facial proportions, "
        "front-facing master reference, clean readable silhouette, coherent outfit. "
        "Neutral clear background, no text, no watermarks. " + style_prompt
    )
    return Shot(id="ref_" + char.id, text="Character reference sheet", location="studio",
                camera="medium", characters=[char.id], duration_seconds=5.0,
                seed=char.seed, prompt=prompt,
                negative_prompt="different faces, multiple unrelated characters, extra arms, text")


def _run_stage(client: ComfyClient, stage: Stage, shot: Shot, where: Path,
               aspect_ratio: str, resolution: str, fps: int,
               refs: list[str] | None = None) -> tuple[Path, list[Path], str]:
    where.mkdir(parents=True, exist_ok=True)
    graph = bind_workflow(stage.workflow, stage.bindings, shot,
                          aspect_ratio=aspect_ratio, resolution=resolution,
                          fps=fps, reference_images=refs)
    (where / "workflow.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    prompt_id = client.queue(graph)
    (where / "job.json").write_text(
        json.dumps({"prompt_id": prompt_id, "stage": stage.name,
                    "shot": shot.id}, ensure_ascii=False, indent=2), encoding="utf-8")
    job = client.wait(prompt_id)
    files = client.download_outputs(job, where / "media")
    selected = _single_file(files, VIDEO_EXTS if stage.name == "video" else IMAGE_EXTS,
                            stage.name)
    return selected, files, prompt_id


def _validate_identity_bindings(project: Project, keyframe: Stage, video: Stage) -> None:
    # Cada personaje debe participar como referencia de imagen, no solo texto.
    if not any(s in video.bindings for s in ("start_frame", "reference_image")):
        raise ValueError("El workflow video debe enlazar start_frame o reference_image")
    for shot in project.shots:
        count = len(shot.characters)
        if count > 4:
            raise ValueError(f"{shot.id}: máximo cuatro identidades por plano en esta versión")
        for index in range(count):
            field = "reference_image" if index == 0 else f"reference_image_{index + 1}"
            if field not in keyframe.bindings:
                raise ValueError(
                    f"{shot.id}: falta binding {field} en keyframe; no se garantiza "
                    "identidad de todos los personajes sin sus referencias.")


def produce(script_path: str | Path, cast_path: str | Path | None,
            config_path: str | Path, output_dir: str | Path,
            *, execute: bool = False, resume: bool = False,
            client: ComfyClient | None = None) -> dict:
    """Ejecuta una producción guiada por configuración, sin pasos manuales entre planos.

    execute=False crea plan y valida el contrato sin invocar modelos.
    execute=True requiere modelos reales cargados en ComfyUI; es opt-in.
    """
    source_file = Path(script_path).resolve()
    config_file = Path(config_path).resolve()
    cast_file = Path(cast_path).resolve() if cast_path else None
    cfg = _read_json(config_file)
    if not isinstance(cfg, dict) or cfg.get("version") != 1:
        raise ValueError("Se requiere config JSON con version: 1")
    if not source_file.is_file():
        raise FileNotFoundError(source_file)
    text = source_file.read_text(encoding="utf-8")
    language_model = cfg.get("ollama_model")
    cast = load_cast(cast_file) if cast_file else None
    interpreted = None
    if language_model:
        if not execute:
            raise ValueError("Con Ollama, la planificación requiere --execute; "
                             "si solo quieres validar, omite ollama_model.")
        interpreted, discovered = interpret_with_ollama(
            text, model=str(language_model),
            endpoint=str(cfg.get("ollama_endpoint", "http://127.0.0.1:11434")))
        if cast is None:
            cast = discovered
    project = make_project(
        text, title=str(cfg.get("title") or source_file.stem),
        style=str(cfg.get("style", "manga_monochrome")),
        aspect_ratio=str(cfg.get("aspect_ratio", "9:16")),
        cast=cast, interpreted=interpreted)
    workdir = Path(output_dir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    plan_path = project.save(workdir)
    if len(project.shots) > int(cfg.get("max_shots", 36)):
        raise ValueError("El libreto produce más planos de los permitidos en la configuración")
    if not project.characters:
        raise ValueError("No se detectó reparto. Proporciona --cast o configura Ollama local.")

    root = config_file.parent
    reference_stage = _stage(root, cfg, "character", required=False)
    keyframe_stage = _stage(root, cfg, "keyframe")
    video_stage = _stage(root, cfg, "video")
    assert keyframe_stage and video_stage
    _validate_identity_bindings(project, keyframe_stage, video_stage)
    resolution = str(cfg.get("resolution", "720p"))
    voice_cfg = cfg.get("voice", {"engine": "off"})
    if not isinstance(voice_cfg, dict) or voice_cfg.get("engine", "off") not in ("off", "piper"):
        raise ValueError("voice.engine debe ser 'off' o 'piper'")
    fps = int(cfg.get("fps", 24))
    if fps < 1 or fps > 60:
        raise ValueError("fps permitido: 1 a 60")
    from .comfy import dimensions
    dimensions(project.aspect_ratio, resolution)
    assets = [_reference_path(c, cast_file) for c in project.characters]
    if reference_stage is None:
        lacking = [ch.name for ch, asset in zip(project.characters, assets) if asset is None]
        if lacking:
            raise ValueError("Faltan imágenes maestras para " + ", ".join(lacking) +
                             "; aporta reference_image en el reparto o configura "
                             "el workflow character para generar referencias reales.")

    cfg_hash = _fingerprint([source_file, config_file] +
                            ([cast_file] if cast_file else []) +
                            [asset for asset in assets if asset is not None] +
                            [root / cfg[name][field] for name in
                             ("keyframe", "video") + (("character",) if reference_stage else ())
                             for field in ("workflow", "bindings")],
                            {"style": project.style, "format": project.aspect_ratio, "fps": fps})
    state_file = workdir / "production_state.json"
    if state_file.exists():
        old = _read_json(state_file)
        if old.get("fingerprint") != cfg_hash:
            raise ValueError("Configuración o libreto cambiaron. Usa otra carpeta de salida.")
        if not resume:
            raise FileExistsError("Ya hay un trabajo. Usa --resume o una carpeta de salida nueva.")
        state = old
    else:
        state = {"version": 1, "fingerprint": cfg_hash, "status": "prepared",
                 "shots": {}, "characters": {}, "warnings": list(project.warnings)}
    if resume and state.get("status") == "completed":
        final = Path(str(state.get("episode", "")))
        if final.is_file() and final.stat().st_size > 1000:
            return {"plan": str(plan_path), "shots": len(project.shots),
                    "characters": len(project.characters), "status_file": str(state_file),
                    "executed": True, "status": "completed", "episode": str(final),
                    "resumed": True}
    _save_state(state_file, state)
    result = {"plan": str(plan_path), "shots": len(project.shots),
              "characters": len(project.characters),
              "status_file": str(state_file), "executed": execute}
    if not execute:
        return result

    endpoint = local_url(str(cfg.get("comfy_endpoint", "http://127.0.0.1:8188")))
    worker = client if client is not None else ComfyClient(endpoint)
    if not worker.health():
        raise RuntimeError(f"ComfyUI local no responde en {endpoint}; comprueba el servicio y los modelos")
    state["status"] = "running"
    _save_state(state_file, state)
    char_by_id = {char.id: char for char in project.characters}
    asset_by_id = {c.id: asset for c, asset in zip(project.characters, assets)}
    uploaded: dict[str, str] = {}
    from .core import STYLE_GUIDES
    style_prompt = STYLE_GUIDES[project.style]["positive"]
    try:
        narrations = {}
        if voice_cfg.get("engine") == "piper":
            from .voice import make_narration
            narrations = make_narration(
                project.shots, workdir / "narracion",
                language=str(voice_cfg.get("language", "es")),
                rate=float(voice_cfg.get("rate", 1.0)))
        for ch in project.characters:
            saved = state["characters"].get(ch.id)
            if saved and Path(saved["asset"]).is_file():
                asset = Path(saved["asset"])
            else:
                asset = asset_by_id[ch.id]
                if asset is None:
                    assert reference_stage is not None
                    shot = _character_shot(ch, style_prompt)
                    asset, _, _ = _run_stage(worker, reference_stage, shot,
                                             workdir / "references" / ch.id,
                                             "1:1", resolution, fps)
                state["characters"][ch.id] = {"asset": str(asset), "seed": ch.seed}
                _save_state(state_file, state)
            uploaded[ch.id] = worker.upload_image(asset)

        all_clips: list[Path] = []
        for shot in project.shots:
            existing = state["shots"].get(shot.id, {})
            if existing.get("status") == "completed" and Path(existing["video"]).is_file():
                all_clips.append(Path(existing["video"]))
                continue
            shot_dir = workdir / "shots" / shot.id
            refs = [uploaded[name] for name in shot.characters if name in uploaded]
            if len(refs) != len(shot.characters):
                raise ValueError(f"{shot.id}: falta referencia de personaje")
            keyframe, _, _ = _run_stage(
                worker, keyframe_stage, shot, shot_dir / "keyframe",
                project.aspect_ratio, resolution, fps, refs=refs)
            state["shots"][shot.id] = {"status": "keyframe_ready", "keyframe": str(keyframe)}
            _save_state(state_file, state)
            starter = worker.upload_image(keyframe)
            motion = replace(
                shot, prompt=shot.prompt +
                ". ANIMATE FROM THE PROVIDED FIRST FRAME. Preserve the exact face, "
                "outfit, architecture and camera geometry. Maintain real temporal motion "
                "without morphing, identity swaps or static slideshow transitions.")
            video, _, _ = _run_stage(
                worker, video_stage, motion, shot_dir / "motion",
                project.aspect_ratio, resolution, fps, refs=[starter])
            report = check_clip(video, shot.duration_seconds, target_ratio=project.aspect_ratio)
            (shot_dir / "quality_report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            if report["warnings"] and bool(cfg.get("strict_quality", True)):
                raise RuntimeError(
                    f"{shot.id} requiere corrección visual/técnica: " +
                    "; ".join(report["warnings"]) +
                    f". Revisa {shot_dir / 'quality_report.json'}")
            finished_video = video
            if shot.id in narrations:
                from .voice import attach_narration
                finished_video = attach_narration(
                    video, narrations[shot.id], shot_dir / "con_voz.mp4")
            state["shots"][shot.id] = {
                "status": "completed", "video": str(finished_video),
                "silent_video": str(video), "keyframe": str(keyframe),
                "quality": report}
            _save_state(state_file, state)
            all_clips.append(finished_video)
        final = assemble(all_clips, workdir / "episodio.mp4")
        state["status"] = "completed"
        state["episode"] = str(final)
        _save_state(state_file, state)
        result.update(status="completed", episode=str(final))
        return result
    except Exception as exc:
        state["status"] = "failed"
        state["last_error"] = str(exc)
        _save_state(state_file, state)
        raise
