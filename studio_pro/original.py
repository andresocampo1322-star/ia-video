"""Adaptador de texto libre a Stickman IA ORIGINAL: sin ComfyUI ni modelos de video.

Convierte un libreto en el esquema de escenas existente. El dibujo/render, poses,
narración Piper y MP4 se ejecutan con el motor del autor. La interpretación del
texto es heurística; NO crea anime neuronal ni texturas fotorrealistas.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from .core import Character, discover_names, load_cast, slug, split_script


def _cast(text: str, cast_file: str | Path | None) -> list[Character]:
    if cast_file:
        characters = load_cast(cast_file)
    else:
        names = discover_names(text)
        characters = [Character(id=slug(n)[:24], name=n) for n in names]
        if not characters:
            characters = [Character(id="protagonista", name="Protagonista")]
    if len(characters) > 4:
        raise ValueError("El motor Stickman original admite hasta 4 personajes por episodio")
    return characters


def _present(text: str, character: Character, index: int) -> bool:
    low = text.casefold()
    name = character.name.casefold()
    if re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", low):
        return True
    if index == 0:
        return any(x in low for x in ("muchacho", "joven", "chico", "protagonista",
                                      "él ", "su casa", "casa", "habitación", "televisión"))
    if any(x in name for x in ("vecina", "marta", "señora", "infectad")):
        return any(x in low for x in ("vecina", "marta", "señora", "infectad", "ella "))
    return False


def _environment(text: str, previous: str) -> str:
    low = text.casefold()
    if any(x in low for x in ("cerca", "patio", "jardín", "jardin",
                              "acera", "calle", "corriendo por fuera", "exterior")):
        return "street"
    if any(x in low for x in ("salón", "habitacion", "habitación", "cocina", "nevera",
                              "televisión", "televisor", "sala", "apartamento",
                              "puerta de la vecina", "puerta de su casa")):
        return "room"
    # 'No fue al supermercado' no significa que la escena ocurra allí.
    if any(x in low for x in ("dentro del supermercado", "entra al supermercado",
                              "interior del supermercado", "pasillo del supermercado")):
        return "supermarket"
    if any(x in low for x in ("bosque", "selva")):
        return "forest"
    return previous if previous != "none" else "room"


def _camera(text: str, has_motion: bool) -> str:
    low = text.casefold()
    if any(x in low for x in ("sangre", "nariz", "ojos", "rostro", "mirada",
                              "primer plano", "pálid", "palid")):
        return "zoom_in"
    if any(x in low for x in ("salta", "brinca", "cae", "rueda", "rodando")):
        return "pan_right"
    if has_motion:
        return "follow"
    if any(x in low for x in ("ciudad", "calle", "paisaje")):
        return "zoom_out"
    return "static"


def _action(text: str, name: str, is_main: bool) -> tuple[str, str, list[dict], str]:
    low = text.casefold()
    attack = any(x in low for x in ("ataca", "ataque", "se lanza", "embiste",
                                     "muerde", "agrede"))
    run = any(x in low for x in ("corre", "corriendo", "huye", "persigu", "escapa",
                                  "persecuci", "salta la cerca", "saltar la cerca"))
    jump = any(x in low for x in ("salta", "salto", "brinca"))
    fall = any(x in low for x in ("cae de cara", "cayó de cara", "rueda", "rodando",
                                   "se estrella"))
    fear = any(x in low for x in ("susto", "miedo", "aterrad", "asustad", "temor",
                                   "desesperad"))
    sick = any(x in low for x in ("pálid", "palid", "nariz", "sangre", "infectad",
                                   "extrañ", "tamabale", "tambalea"))
    move: list[dict] = []
    if is_main:
        pose = "think"
        expression = "surprised" if fear or attack or fall else "thinking"
        gait = "run" if run else "walk"
        if run:
            move.append({"at": 0.08, "move_to": 0.80})
        elif any(x in low for x in ("camina", "sale", "entra", "acerca", "se dirige")):
            move.append({"at": 0.15, "move_to": 0.25})
        if jump:
            move.append({"at": 0.55, "pose": "jump"})
            move.append({"at": 0.88, "pose": "guard"})
        elif fear:
            move.append({"at": 0.50, "pose": "cower"})
        return pose, expression, move, gait
    pose = "stagger" if sick else "idle"
    expression = "angry" if attack else "surprised" if sick else "neutral"
    gait = "run" if attack or run else "sneak" if sick else "walk"
    if attack or run:
        move.append({"at": 0.15, "pose": "attack", "move_to": -0.30})
    if jump:
        move.append({"at": 0.60, "pose": "jump"})
    if fall:
        move.append({"at": 0.82, "pose": "stagger"})
    return pose, expression, move, gait


def _cast_preset(character: Character, index: int) -> dict:
    desc = (character.appearance + " " + character.clothing).casefold()
    hair = ("long" if any(x in desc for x in ("largo", "larga", "long hair"))
            else "curly" if any(x in desc for x in ("rizado", "rizos"))
            else "none" if any(x in desc for x in ("calvo", "sin cabello"))
            else "short")
    color = ("#4F6178" if index == 0 else "#A9A8A1" if "pálid" in desc
             else "#647A65" if index == 1 else "#8C6A7F")
    return {"id": character.id[:24], "name": character.name,
            "preset": {"hair": hair, "hair_color": "#211F21",
                       "color": color, "accessory": "none"}}


def build_original_script(text: str, *,
                          cast_file: str | Path | None = None,
                          title: str = "Episodio de ia-video"):
    """Devuelve Script Pydantic validado, sin generar ni fingir fotogramas."""
    from stickman.schema import validate_script

    segments = split_script(text)
    if len(segments) > 24:
        raise ValueError("Este motor admite hasta 24 escenas; divide la historia en dos episodios")
    chars = _cast(text, cast_file)
    visual_cast = [_cast_preset(c, index) for index, c in enumerate(chars)]
    raw_scenes = []
    previous = "room"
    previous_actors: set[str] = set()
    for i, segment in enumerate(segments):
        low = segment.casefold()
        env = _environment(segment, previous)
        # Persistencia del escenario, no inventar un supermercado por una mención.
        previous = env
        is_attack = any(v in low for v in ("ataca", "ataque", "se lanza", "embiste"))
        is_flee = any(v in low for v in ("corre", "huye", "persigu", "salta", "escapa"))
        motion = is_attack or is_flee or any(
            v in low for v in ("camina", "sale", "entra", "se acerca"))
        detected = [c for j, c in enumerate(chars) if _present(segment, c, j)]
        if not detected:
            detected = [chars[0]]
        # No inventar multitudes: el motor permite 3 personajes por plano.
        detected = detected[:3]
        scene_actors = []
        for character in detected:
            is_main = character.id == chars[0].id
            pose, expr, acts, gait = _action(segment, character.name, is_main)
            scene_actors.append({
                "id": character.id[:24], "x": -0.64 if is_main else 0.63,
                "facing": "right" if is_main else "left",
                "pose": pose, "expression": expr,
                "gait": gait, "movement_ease": "ease_in_out",
                "continue_from_previous": (env == raw_scenes[-1]["environment"]
                                           and character.id in previous_actors)
                                          if raw_scenes else False,
                "actions": acts,
            })
        events = []
        if any(v in low for v in ("televisi", "noticiero", "televisor",
                                   "emergencia", "disturbios", "noticias", "alerta")):
            events.append({"text": "ALERTA DE EMERGENCIA", "at": 0.15, "until": 0.65})
        elif "nariz" in low and "sangre" in low:
            events.append({"text": "ALGO NO ESTÁ BIEN", "at": 0.45, "until": 0.82})
        elif is_attack:
            events.append({"text": "¡CORRE!", "at": 0.55, "until": 0.87})
        scenery = {
            "room": "noche" if ("noche" in low or "oscuro" in low) else "lavanda",
            "street": "noche" if ("noche" in low or "oscur" in low) else "cielo",
            "supermarket": "cielo", "forest": "menta",
        }
        props = []
        if "teléfono" in low or "telefono" in low or "celular" in low:
            props = [{"type": "phone", "holder": chars[0].id[:24], "at": 0.3}]
        raw_scenes.append({
            "id": f"s{i + 1:02d}", "narration": segment[:700],
            "speaker": "narrador", "background": scenery.get(env, "papel"),
            "environment": env, "atmosphere": "rain" if "lluvia" in low else "none",
            "camera": _camera(segment, motion),
            "transition": "fade_from_black" if i == 0 else "cut",
            "characters": scene_actors, "props": props, "keywords": events,
        })
        previous_actors = {c["id"] for c in scene_actors}
    validated, warnings = validate_script({
        "title": title, "language": "es", "cast": visual_cast,
        "scenes": raw_scenes})
    if warnings:
        raise ValueError("El adaptador produjo un guion inválido: " + "; ".join(warnings))
    return validated


def render_original(text: str, output: str | Path, *,
                    cast_file: str | Path | None = None,
                    title: str = "Episodio de ia-video",
                    execute: bool = True,
                    fps: int = 24, render_scale: float = 0.65,
                    log: Callable[[str], None] | None = None,
                    progress: Callable[[str, float], None] | None = None) -> dict:
    """Usa el render del autor, nunca genera un MP4 ficticio."""
    script = build_original_script(text, cast_file=cast_file, title=title)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    screenplay = out / "guion_stickman.json"
    screenplay.write_text(script.to_json(), encoding="utf-8")
    if not execute:
        return {"status": "validated", "script": str(screenplay),
                "scenes": len(script.scenes), "engine": "stickman_original"}
    from stickman.pipeline import render_script

    result = render_script(
        script, out, fmt="9:16", engine="piper",
        fps=fps, render_scale=render_scale,
        max_seconds=300, word_align=False,
        basename="episodio_stickman",
        log=log or print, progress=progress)
    mp4 = Path(result["mp4"])
    if not mp4.is_file() or mp4.stat().st_size < 1000:
        raise RuntimeError("El render terminó sin producir un MP4 válido")
    return {"status": "completed", "engine": "stickman_original",
            "scenes": len(script.scenes), "mp4": str(mp4),
            "script": str(screenplay), "duration": result["duration"]}
