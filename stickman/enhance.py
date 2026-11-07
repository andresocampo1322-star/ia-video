"""Mejora opcional y conservadora de movimiento para guiones existentes.

No sustituye Skia, Piper, FFmpeg, los dibujos ni el motor de escenas.
La función es pura con respecto al guion recibido: devuelve una copia.
"""
from __future__ import annotations

from .schema import Script


def enhance_script(script: Script) -> Script:
    """Enriquece parámetros *opt-in* de movimiento usando solo el guion validado.

    Reglas conservadoras:
    - Suavizar un desplazamiento solicitado sin cambiar sus puntos de inicio/fin.
    - Seguir al personaje solo en una escena con exactamente un personaje móvil
      y cámara originalmente estática.
    - Continuar posición/orientación solo entre escenas con el mismo fondo y
      personaje, sin salida/entrada explícita.
    Las escenas que no satisfacen estas condiciones no cambian de comportamiento.
    """
    enhanced = script.model_copy(deep=True)
    for index, scene in enumerate(enhanced.scenes):
        previous = enhanced.scenes[index - 1] if index > 0 else None
        for ch in scene.characters:
            moving = any(a.move_to is not None for a in ch.actions)
            if moving and ch.movement_ease == "linear":
                ch.movement_ease = "ease_in_out"
            if (previous is not None and scene.background == previous.background and
                    scene.environment == previous.environment and
                    ch.enter == "none" and not ch.continue_from_previous):
                prev_ch = next((p for p in previous.characters if p.id == ch.id), None)
                if prev_ch is not None and prev_ch.exit == "none":
                    ch.continue_from_previous = True
        if (scene.camera == "static" and len(scene.characters) == 1 and
                any(a.move_to is not None for a in scene.characters[0].actions)):
            scene.camera = "follow"
    return enhanced
