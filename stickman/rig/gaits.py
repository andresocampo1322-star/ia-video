"""Ciclos alternativos de locomoción (opt-in).

Estos ciclos complementan walk_overlay() en poses.py; nunca lo sustituyen.
Los ángulos están expresados en grados, con el rig original intacto.
"""
from __future__ import annotations

import math
from typing import Dict


def run_overlay(phase: float) -> Dict[str, float]:
    """Carrera: zancada y braceo más amplios, leve inclinación hacia delante."""
    s, c = math.sin(phase), math.cos(phase)
    return {
        "l_hip": 90 + 34 * s,
        "r_hip": 90 - 34 * s,
        "l_knee": max(0.0, -c) * 54,
        "r_knee": max(0.0, c) * 54,
        "l_sh": 90 - 37 * s,
        "r_sh": 90 + 37 * s,
        "l_el": -36,
        "r_el": -36,
        "spine": -83.0,
    }


def sneak_overlay(phase: float) -> Dict[str, float]:
    """Avance sigiloso: zancada corta, rodillas flexionadas y poca elevación."""
    s, c = math.sin(phase), math.cos(phase)
    return {
        "l_hip": 90 + 15 * s,
        "r_hip": 90 - 15 * s,
        "l_knee": 30 + max(0.0, -c) * 18,
        "r_knee": 30 + max(0.0, c) * 18,
        "l_sh": 75 - 10 * s,
        "r_sh": 75 + 10 * s,
        "l_el": -48,
        "r_el": -48,
        "spine": -76.0,
    }
