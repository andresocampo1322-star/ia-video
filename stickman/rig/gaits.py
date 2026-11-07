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
        "l_hip": 90 + 43 * s,
        "r_hip": 90 - 43 * s,
        "l_knee": max(0.0, -c) * 62,
        "r_knee": max(0.0, c) * 62,
        "l_sh": 90 - 44 * s,
        "r_sh": 90 + 44 * s,
        "l_el": -38,
        "r_el": -38,
        "spine": -82.0,
    }


def sneak_overlay(phase: float) -> Dict[str, float]:
    """Avance sigiloso: zancada corta, rodillas flexionadas y poca elevación."""
    s, c = math.sin(phase), math.cos(phase)
    return {
        "l_hip": 90 + 15 * s,
        "r_hip": 90 - 15 * s,
        "l_knee": 20 + max(0.0, -c) * 24,
        "r_knee": 20 + max(0.0, c) * 24,
        "l_sh": 90 - 9 * s,
        "r_sh": 90 + 9 * s,
        "l_el": -24,
        "r_el": -24,
        "spine": -86.0,
    }
