"""Escenarios/clima opt-in, invariancia visual del modo original y Skia real."""
import hashlib

import numpy as np
import skia

from stickman.enhance import enhance_script
from stickman.render import VideoRenderer
from stickman.scenery import draw_atmosphere
from stickman.schema import validate_script

ENVIRONMENTS = ("street", "room", "supermarket", "forest")
WEATHERS = ("rain", "snow", "fog")


def make(env=None, weather=None, *, fmt="16:9"):
    s = {"narration": "Una escena.", "background": "cielo",
         "characters": [{"id": "a", "x": 0.0, "pose": "wave"}]}
    if env is not None:
        s["environment"] = env
    if weather is not None:
        s["atmosphere"] = weather
    script, warnings = validate_script({
        "title": "prueba", "cast": [{"id": "a"}], "scenes": [s]})
    assert not warnings, warnings
    return VideoRenderer(script, fmt, [2.0], np.zeros(48, np.float32), [],
                         fps=24, render_scale=0.45)


def test_legacy_unchanged_when_options_omitted(tmp_path):
    legacy = make()
    explicit = make("none", "none")
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    for frame in (0, 12, 35):
        legacy.snapshot(frame, str(a))
        explicit.snapshot(frame, str(b))
        assert hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()


def test_all_four_environments_draw_without_replacing_characters(tmp_path):
    default = make()
    p = tmp_path / "baseline.png"
    default.snapshot(2, str(p))
    baseline = hashlib.sha256(p.read_bytes()).digest()
    for env in ENVIRONMENTS:
        r = make(env)
        assert len(r.scenes[0].chars) == len(default.scenes[0].chars) == 1
        r.snapshot(2, str(p))
        assert p.stat().st_size > 2500
        assert hashlib.sha256(p.read_bytes()).digest() != baseline


def test_all_atmospheres_render_at_both_aspect_ratios(tmp_path):
    for fmt in ("9:16", "16:9"):
        for weather in WEATHERS:
            r = make("street", weather, fmt=fmt)
            path = tmp_path / (weather + fmt.replace(":", "-") + ".png")
            r.snapshot(13, str(path))
            assert path.stat().st_size > 2000


def test_rain_is_deterministic_but_changes_over_time(tmp_path):
    def snapshot(t):
        surface = skia.Surface(360, 240)
        c = surface.getCanvas()
        c.clear(skia.ColorWHITE)
        draw_atmosphere(c, "rain", 360, 240, 180, t, "#DCE7F2")
        f = tmp_path / f"t{t}.png"
        surface.makeImageSnapshot().save(str(f))
        return hashlib.sha256(f.read_bytes()).digest()
    assert snapshot(0.0) == snapshot(0.0)
    assert snapshot(0.0) != snapshot(0.75)


def test_new_background_fields_are_validated():
    script, warnings = validate_script({"scenes": [{
        "narration": "Un lugar nuevo.",
        "environment": "market", "atmosphere": "lluvia"}]})
    assert not warnings
    assert script.scenes[0].environment == "supermarket"
    assert script.scenes[0].atmosphere == "rain"
    script, warnings = validate_script({"scenes": [{
        "narration": "Color.",
        "environment": "mars", "atmosphere": "hurricane"}]})
    assert warnings and script.scenes[0].environment == "none"
    assert script.scenes[0].atmosphere == "none"


def test_auto_continuity_respects_location_changes():
    script, warnings = validate_script({"cast": [{"id": "nora"}], "scenes": [
        {"narration": "Calle.", "background": "noche", "environment": "street",
         "characters": [{"id": "nora", "x": -0.2}]},
        {"narration": "Interior.", "background": "noche", "environment": "supermarket",
         "characters": [{"id": "nora", "x": 0.4}]}
    ]})
    assert not warnings
    out = enhance_script(script)
    assert out.scenes[1].characters[0].continue_from_previous is False
    assert script.scenes[1].characters[0].continue_from_previous is False
