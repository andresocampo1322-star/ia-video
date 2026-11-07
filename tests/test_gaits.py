"""Regresiones del motor original y pruebas de locomoción opcional."""
import math

import numpy as np
import pytest
from pydantic import ValidationError

from stickman.rig.gaits import run_overlay, sneak_overlay
from stickman.rig.poses import walk_overlay
from stickman.render import VideoRenderer
from stickman.schema import SceneCharacter, validate_script


def make_renderer(gait=None):
    ch = {"id": "a", "x": -0.7, "actions": [{"at": 0.0, "move_to": 0.7}]}
    if gait:
        ch["gait"] = gait
    raw = {"title": "Prueba", "cast": [{"id": "a"}],
           "scenes": [{"narration": "El personaje avanza.", "characters": [ch]}]}
    script, warnings = validate_script(raw)
    assert not warnings
    return VideoRenderer(script, "16:9", [3.0], np.zeros(90, np.float32), [], fps=30)


def test_original_walk_overlay_is_unmodified():
    # Muestra de referencia del ciclo original, previa a esta ampliación.
    j = walk_overlay(0.0)
    assert j == {
        "l_hip": 90.0, "r_hip": 90.0,
        "l_knee": 0.0, "r_knee": 38.0,
        "l_sh": 90.0, "r_sh": 90.0,
        "l_el": -18, "r_el": -18, "spine": -87.0,
    }


def test_schema_defaults_to_original_walk_and_rejects_invalid_gait():
    assert SceneCharacter(id="a").gait == "walk"
    assert SceneCharacter(id="a", gait="run").gait == "run"
    assert SceneCharacter(id="a", gait="sneak").gait == "sneak"
    with pytest.raises(ValidationError):
        SceneCharacter(id="a", gait="fly")


def test_new_gaits_are_finite_and_distinct():
    for phase in [0.0, 0.3, 0.9, math.pi, 5.4]:
        walk = walk_overlay(phase)
        run = run_overlay(phase)
        sneak = sneak_overlay(phase)
        assert run.keys() == walk.keys() == sneak.keys()
        assert all(math.isfinite(x) for j in (run, sneak) for x in j.values())
    assert run_overlay(math.pi / 2)["l_hip"] > walk_overlay(math.pi / 2)["l_hip"]
    assert sneak_overlay(math.pi / 2)["l_hip"] < walk_overlay(math.pi / 2)["l_hip"]


def test_movement_speeds_change_only_when_opted_in():
    original, default_walk = make_renderer(), make_renderer("walk")
    run, sneak = make_renderer("run"), make_renderer("sneak")
    def duration(renderer):
        return renderer.scenes[0].chars[0].moves[0].dur
    assert duration(original) == duration(default_walk)
    assert duration(run) < duration(original) < duration(sneak)


def test_default_frames_equal_explicit_walk():
    original, walk = make_renderer(), make_renderer("walk")
    for frame in [0, 9, 18, 27, 45, 70]:
        t = frame / 30
        a = original._char_frame(original.scenes[0].chars[0], t, frame, 3.0)
        b = walk._char_frame(walk.scenes[0].chars[0], t, frame, 3.0)
        assert a.joints == b.joints
        assert a.lift == b.lift
        assert a.x == b.x
        assert a.facing == b.facing
