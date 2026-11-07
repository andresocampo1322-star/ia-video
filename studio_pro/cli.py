"""CLI independiente de producción avanzada: python -m studio_pro.

No intercepta `python -m stickman`; usar las nuevas funciones es opt-in.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .comfy import ComfyClient, bind_workflow, load_api_workflow, load_bindings
from .core import Character, Project, Shot, STYLE_GUIDES, load_cast, make_project
from .ollama import interpret_with_ollama
from .skills import get_skills, validate_skill_graph


def _load_project(path: str) -> Project:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    chars = [Character(**x) for x in data["characters"]]
    shots = [Shot(**x) for x in data["shots"]]
    return Project(title=data["title"], style=data["style"],
                   aspect_ratio=data["aspect_ratio"], source_text=data["source_text"],
                   characters=chars, shots=shots,
                   interpreter=data.get("interpreter", "heuristic"),
                   warnings=data.get("warnings", []))


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m studio_pro",
                                 description="Pipeline opcional para producción generativa de ia-video")
    command = ap.add_subparsers(dest="command", required=True)
    command.add_parser("skills", help="Mostrar skills y su estado real")
    plan = command.add_parser("plan", help="Libreto -> biblia visual y prompts por plano")
    plan.add_argument("--script", required=True, help="Archivo de libreto UTF-8")
    plan.add_argument("--cast", help="JSON con descripción e imágenes de referencia")
    plan.add_argument("--title", default="Nuevo episodio")
    plan.add_argument("--style", choices=sorted(STYLE_GUIDES), default="manga_monochrome")
    plan.add_argument("--format", choices=("9:16", "16:9", "1:1"), default="9:16")
    plan.add_argument("--out", default="salida_pro")
    plan.add_argument("--ollama-model", default=None,
                      help="Modelo local de Ollama para interpretación semántica")
    plan.add_argument("--ollama-url", default="http://127.0.0.1:11434")

    render = command.add_parser("render-project", help="Vincular o ejecutar workflow API de ComfyUI")
    render.add_argument("--project", required=True, help="production_plan.json")
    render.add_argument("--workflow", required=True, help="Workflow de ComfyUI en formato API")
    render.add_argument("--bindings", required=True, help="JSON con node+input por variable")
    render.add_argument("--out", default="salida_pro/workflows")
    render.add_argument("--resolution", choices=("540p", "720p", "1080p"), default="720p")
    render.add_argument("--fps", type=int, default=24)
    render.add_argument("--shot", help="Procesar solo shot_001, etc.")
    render.add_argument("--reference-filename", default=None,
                        help="Archivo de referencia ya presente en ComfyUI/input")
    render.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    render.add_argument("--submit", action="store_true", help="Enviar a ComfyUI: ejecutar modelos")
    render.add_argument("--wait", action="store_true", help="Esperar y descargar resultados")
    edit = command.add_parser("assemble", help="Unir clips generados en un episodio MP4")
    edit.add_argument("--jobs", help="Manifiesto jobs.json de un render completado")
    edit.add_argument("--clip", action="append", help="Video en orden; repetir por cada plano")
    edit.add_argument("--out", required=True, help="Archivo MP4 resultante")
    edit.add_argument("--force", action="store_true", help="Sobrescribir salida si ya existe")
    prod = command.add_parser("produce", help="Generar episodio desde libreto con ComfyUI real")
    prod.add_argument("--script", required=True, help="Archivo de libreto en texto UTF-8")
    prod.add_argument("--cast", help="Biblia JSON de personajes con referencias opcionales")
    prod.add_argument("--config", required=True, help="Configuración de workflows API de ComfyUI")
    prod.add_argument("--out", default="salida_pro/episodio_nuevo")
    prod.add_argument("--execute", action="store_true",
                      help="Generar imagenes y videos con modelos reales; requiere servidor")
    prod.add_argument("--resume", action="store_true", help="Continuar un trabajo interrumpido")
    original = command.add_parser("original", help="Libre-to-MP4 con Stickman IA original y Piper")
    original.add_argument("--script", required=True, help="Historia TXT (párrafos = escenas)")
    original.add_argument("--cast", help="Personajes JSON opcionales")
    original.add_argument("--out", default="salida/episodio_stickman")
    original.add_argument("--title", default="Episodio de ia-video")
    original.add_argument("--fps", type=int, default=24)
    original.add_argument("--scale", type=float, default=0.65)
    original.add_argument("--execute", action="store_true",
                          help="Renderiza con Piper y motor original; por defecto solo valida")
    command.add_parser("gui", help="Interfaz de produccion avanzada (no sustituye Stickman)")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = _build_parser()
    args = ap.parse_args(argv)
    if args.command == "original":
        from .original import render_original
        result = render_original(
            Path(args.script).read_text(encoding="utf-8"),
            args.out, cast_file=args.cast, title=args.title,
            execute=args.execute, fps=args.fps, render_scale=args.scale,
            log=print, progress=lambda stage, p: print(f"{stage}: {p:.1%}", flush=True))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "gui":
        from .gui import main as gui_main
        gui_main()
        return 0
    if args.command == "produce":
        from .production import produce
        result = produce(args.script, args.cast, args.config, args.out,
                         execute=args.execute, resume=args.resume)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("episode"):
            print("EPISODIO MP4:", result["episode"])
        else:
            print("Preflight correcto; sin modelos ejecutados. Usa --execute para render real.")
        return 0
    if args.command == "skills":
        validate_skill_graph()
        print(json.dumps(get_skills(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "plan":
        raw = Path(args.script).read_text(encoding="utf-8")
        cast = load_cast(args.cast) if args.cast else None
        interpreted = None
        if args.ollama_model:
            interpreted, candidates = interpret_with_ollama(
                raw, model=args.ollama_model, endpoint=args.ollama_url)
            if cast is None:
                cast = candidates
        project = make_project(raw, title=args.title, style=args.style,
                               aspect_ratio=args.format, cast=cast,
                               interpreted=interpreted)
        file = project.save(args.out)
        print(f"Plan: {file} | {len(project.shots)} planos | {len(project.characters)} personajes")
        for warning in project.warnings:
            print("AVISO:", warning)
        print("No se ha generado video. Usa render-project con un workflow/modelo real.")
        return 0
    if args.command == "assemble":
        from .edit import assemble, clips_from_jobs
        if bool(args.jobs) == bool(args.clip):
            ap.error("Indica --jobs O uno o varios --clip, pero no ambos")
        clips = clips_from_jobs(args.jobs) if args.jobs else args.clip
        final = assemble(clips, args.out, force=args.force)
        print(f"Episodio MP4: {final} ({final.stat().st_size} bytes)")
        return 0
    if args.command == "render-project":
        if args.wait and not args.submit:
            ap.error("--wait requiere --submit")
        project = _load_project(args.project)
        graph = load_api_workflow(args.workflow)
        bindings = load_bindings(args.bindings)
        selected = [s for s in project.shots if not args.shot or s.id == args.shot]
        if not selected:
            ap.error("No existe el identificador --shot indicado")
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        client = ComfyClient(args.comfy_url) if args.submit else None
        result = []
        for shot in selected:
            patched = bind_workflow(graph, bindings, shot,
                                    aspect_ratio=project.aspect_ratio,
                                    resolution=args.resolution, fps=args.fps,
                                    reference_filename=args.reference_filename)
            filename = out / f"{shot.id}_workflow.json"
            filename.write_text(json.dumps(patched, ensure_ascii=False, indent=2),
                                encoding="utf-8")
            record = {"shot": shot.id, "workflow": str(filename), "status": "prepared"}
            if client:
                prompt_id = client.queue(patched)
                record.update(prompt_id=prompt_id, status="queued")
                if args.wait:
                    job = client.wait(prompt_id)
                    files = client.download_outputs(job, out / shot.id)
                    record.update(status="completed", files=[str(f) for f in files])
            print(json.dumps(record, ensure_ascii=False))
            result.append(record)
        (out / "jobs.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        if not args.submit:
            print("Modo seguro: workflows preparados, sin ejecutar modelos ni consumir créditos.")
        return 0
    ap.error("Comando inválido")
    return 2
