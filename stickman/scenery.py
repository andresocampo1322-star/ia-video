"""Escenarios y atmósferas vectoriales OPCIONALES para el renderer Skia.

No sustituye dibujos, esqueleto, guion, voz ni el rasterizador original.
Los fondos usan coordenadas de escenario, por debajo de los personajes.
"""
from __future__ import annotations

import math

import skia

from .rig.draw import hex_color, luminance


def _fill(color: str, alpha: float = 1.0) -> skia.Paint:
    return skia.Paint(AntiAlias=True, Color=hex_color(color, alpha))


def _stroke(color: str, width: float, alpha: float = 1.0) -> skia.Paint:
    return skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                      StrokeWidth=width, Color=hex_color(color, alpha))


def _rect(c: skia.Canvas, x0: float, y0: float, x1: float, y1: float,
          color: str, alpha: float = 1.0) -> None:
    c.drawRect(skia.Rect.MakeLTRB(x0, y0, x1, y1), _fill(color, alpha))


def _line(c: skia.Canvas, x0: float, y0: float, x1: float, y1: float,
          color: str, width: float = 3.0, alpha: float = 1.0) -> None:
    c.drawLine(x0, y0, x1, y1, _stroke(color, width, alpha))


def draw_scenery(c: skia.Canvas, kind: str, width: int, height: int,
                 ground: float, background: str) -> None:
    """Dibuja ilustración vectorial detrás del reparto. `none` no hace nada."""
    if kind == "none":
        return
    unit = height / 1080.0
    night = luminance(background) < 0.35
    outline = "#D6DBE5" if night else "#687889"
    wall = "#3B4858" if night else "#BDCDD8"
    wall2 = "#465367" if night else "#D0DDE4"
    pane = "#E7C58B" if night else "#B8DDEB"
    floor = "#303744" if night else "#D9D5CC"
    _rect(c, -width, ground - 5 * unit, width * 2.0, ground + 320 * unit,
          floor, 0.85)

    if kind == "street":
        for i in range(-8, 15):
            x = i * 265 * unit
            h = (340 + (i % 3) * 64) * unit
            _rect(c, x, ground - h, x + 258 * unit, ground - 10 * unit,
                  wall if i % 2 else wall2)
            _line(c, x, ground - h, x + 258 * unit, ground - h,
                  outline, 3 * unit, 0.45)
            for row in range(3):
                for col in range(2):
                    wx = x + (37 + col * 111) * unit
                    wy = ground - h + (55 + row * 87) * unit
                    _rect(c, wx, wy, wx + 55 * unit, wy + 42 * unit,
                          pane, 0.58 if night else 0.68)
                    _line(c, wx + 27 * unit, wy, wx + 27 * unit, wy + 42 * unit,
                          outline, 2 * unit, 0.36)
            _rect(c, x + 104 * unit, ground - 98 * unit,
                  x + 168 * unit, ground, "#637387" if night else "#E7ECEE")
        for i in range(-2, 5):
            x = (i * 540 + 210) * unit
            _line(c, x, ground, x, ground - 290 * unit, outline, 6 * unit, 0.85)
            _line(c, x, ground - 290 * unit, x + 60 * unit, ground - 290 * unit,
                  outline, 6 * unit, 0.85)
            c.drawCircle(x + 65 * unit, ground - 286 * unit, 16 * unit,
                         _fill("#FFDE9D", 0.78))
        _line(c, -width, ground, width * 2, ground, outline, 3 * unit, 0.5)

    elif kind == "room":
        _line(c, -width, ground - 275 * unit, width * 2, ground - 275 * unit,
              outline, 2 * unit, 0.20)
        _rect(c, width * 0.08, ground - 535 * unit, width * 0.31,
              ground - 280 * unit, "#E0E7ED" if night else "#F5F8F8")
        _rect(c, width * 0.095, ground - 520 * unit, width * 0.295,
              ground - 295 * unit, pane, 0.80)
        _line(c, width * 0.195, ground - 520 * unit,
              width * 0.195, ground - 295 * unit, outline, 4 * unit)
        _line(c, width * 0.095, ground - 407 * unit,
              width * 0.295, ground - 407 * unit, outline, 4 * unit)
        _rect(c, width * 0.69, ground - 415 * unit, width * 0.88,
              ground - 260 * unit, wall)
        _rect(c, width * 0.71, ground - 395 * unit, width * 0.86,
              ground - 285 * unit, "#F1E3C9" if night else "#E7F0EF")
        _rect(c, width * 0.02, ground - 110 * unit, width * 0.35,
              ground - 34 * unit, "#60788D")
        for fx in (width * 0.055, width * 0.30):
            _rect(c, fx, ground - 36 * unit, fx + 20 * unit, ground + 3 * unit,
                  outline)
        _line(c, -width, ground - 9 * unit, width * 2, ground - 9 * unit,
              outline, 3 * unit, 0.45)

    elif kind == "supermarket":
        _rect(c, -width, ground - 520 * unit, width * 2, ground - 470 * unit,
              wall, 0.75)
        for i in range(-3, 9):
            x = i * 395 * unit + 75 * unit
            _rect(c, x, ground - 395 * unit, x + 300 * unit,
                  ground - 25 * unit, "#74889A" if night else "#94A9B6", 0.9)
            _rect(c, x + 14 * unit, ground - 384 * unit,
                  x + 285 * unit, ground - 35 * unit,
                  "#3F4A56" if night else "#E4E8DF")
            for row in range(4):
                py = ground - (354 - row * 81) * unit
                for j in range(6):
                    bx = x + (28 + j * 41) * unit
                    palette = ("#D3977D", "#C9B96D", "#90AFA6", "#AC9CC5")
                    _rect(c, bx, py, bx + 29 * unit, py + 44 * unit,
                          palette[(j + row + i) % 4])
                _rect(c, x + 10 * unit, py + 48 * unit,
                      x + 287 * unit, py + 55 * unit,
                      "#718594" if night else "#85959D")
            _line(c, x, ground - 395 * unit, x + 300 * unit,
                  ground - 395 * unit, outline, 4 * unit)
        _rect(c, width * 0.39, ground - 548 * unit,
              width * 0.61, ground - 467 * unit,
              "#E2E8DF" if night else "#F0F0E5")
        _line(c, width * 0.39, ground - 548 * unit, width * 0.61,
              ground - 548 * unit, outline, 4 * unit)
        _line(c, -width, ground, width * 2, ground, outline, 3 * unit, 0.55)

    elif kind == "forest":
        _rect(c, -width, ground - 145 * unit, width * 2, ground + 5 * unit,
              "#718979" if night else "#C4D9BD", 0.45)
        for i in range(-7, 16):
            x = (i * 225 + 40) * unit
            h = (240 + (i % 4) * 45) * unit
            _rect(c, x - 15 * unit, ground - h, x + 15 * unit,
                  ground + 4 * unit, "#5B665A" if night else "#8C806B")
            top = ground - h
            c.drawCircle(x, top + 22 * unit, 82 * unit,
                         _fill("#3C685E" if night else "#86AB83", 0.83))
            c.drawCircle(x - 45 * unit, top + 70 * unit, 60 * unit,
                         _fill("#54766B" if night else "#9CBD94", 0.82))
            c.drawCircle(x + 40 * unit, top + 75 * unit, 56 * unit,
                         _fill("#3D5D55" if night else "#7DA078", 0.80))
        _line(c, -width, ground, width * 2, ground, outline, 2 * unit, 0.3)


def draw_atmosphere(c: skia.Canvas, kind: str, width: int, height: int,
                    ground: float, t: float, background: str) -> None:
    """Partículas en primer plano; deterministic as a function of time."""
    if kind == "none":
        return
    u = height / 1080.0
    night = luminance(background) < 0.35
    if kind == "rain":
        pen = _stroke("#CEDFED" if night else "#5A7998", 2.0 * u, 0.30)
        for i in range(92):
            x = -width + ((i * 137.2 + 67.3) * u) % (width * 3)
            y = ((i * 73.6 * u + t * 330 * u) % (height * 1.2)) - height * 0.15
            c.drawLine(x, y, x - 14 * u, y + 29 * u, pen)
    elif kind == "snow":
        dot = _fill("#E4F2FA" if night else "#6D95B0", 0.48)
        for i in range(80):
            sway = math.sin(t * 1.1 + i * 1.7) * 16 * u
            x = -width + ((i * 137.2 + 93.3) * u + sway) % (width * 3)
            y = ((i * 57.9 * u + t * 58 * u) % (height * 1.20)) - height * 0.12
            c.drawCircle(x, y, (2.0 + (i % 3)) * u, dot)
    elif kind == "fog":
        fill = _fill("#CFD5DA" if night else "#E9ECE8", 0.095)
        for i in range(5):
            offset = math.sin(t * 0.24 + i) * 30 * u
            x = -width + (i * (width * 0.75)) + offset
            y = ground - (65 + i % 3 * 35) * u
            c.drawOval(skia.Rect.MakeLTRB(x, y - 75 * u,
                                          x + width * 0.95, y + 68 * u), fill)
