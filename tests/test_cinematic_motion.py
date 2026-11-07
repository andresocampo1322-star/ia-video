"""Pruebas de animación incremental: comportamiento previo y cuatro opciones nuevas."""
import hashlib

import numpy as np

from stickman.render import VideoRenderer
from stickman.schema import validate_script


def renderer(scenes, *, durations=None):
    raw = {"title": "Prueba de continuidad", "cast": [
        {"id": "nora", "name": "Nora", "preset": {"color": "#2F6FB0", "hair": "ponytail"}},
    ], "scenes": scenes}
    script, warnings = validate_script(raw)
    assert not warnings, warnings
    durations = durations or [3.0] * len(scenes)
    return VideoRenderer(script, "16:9", durations,
                         np.zeros(round(sum(durations) * 30), np.float32), [],
                         fps=30, render_scale=0.5)


def scene(character, **kwargs):
    return {"narration": "Un plano de prueba.", "characters": [character], **kwargs}


def actor(**kwargs):
    return {"id": "nora", "x": -0.6, **kwargs}


def test_existing_motion_equal_explicit_linear():
    a = renderer([scene(actor(actions=[{"at": 0.0, "move_to": 0.6}]))])
    b = renderer([scene(actor(movement_ease="linear", continue_from_previous=False,
                              actions=[{"at": 0.0, "move_to": 0.6}]),
                        transition="cut", camera="static")])
    ca, cb = a.scenes[0].chars[0], b.scenes[0].chars[0]
    for frame in range(0, 90, 6):
        t = frame / 30
        fa = a._char_frame(ca, t, frame, 3.0)
        fb = b._char_frame(cb, t, frame, 3.0)
        assert (fa.joints, fa.x, fa.lift, fa.face, fa.facing) == (
            fb.joints, fb.x, fb.lift, fb.face, fb.facing)
        assert a._camera_values(a.scenes[0], t) == b._camera_values(b.scenes[0], t)


def test_ease_in_out_starts_and_stops_smoothly():
    raw = renderer([scene(actor(actions=[{"at": 0.0, "move_to": 0.6}]))])
    eased = renderer([scene(actor(movement_ease="ease_in_out",
                                 actions=[{"at": 0.0, "move_to": 0.6}]))])
    c0, c1 = raw.scenes[0].chars[0], eased.scenes[0].chars[0]
    duration = c0.moves[0].dur
    assert c1.moves[0].dur == duration
    assert c1.x_at(duration * 0.25)[0] < c0.x_at(duration * 0.25)[0]
    assert c1.x_at(duration * 0.5)[0] == c0.x_at(duration * 0.5)[0]
    assert c1.x_at(duration * 0.75)[0] > c0.x_at(duration * 0.75)[0]
    assert c1.x_at(duration)[0] == c0.x_at(duration)[0]


def test_continuity_preserves_endpoint_facing_and_blends_expression():
    a = scene(actor(x=-0.5, pose="wave", expression="happy",
                    actions=[{"at": 0.0, "move_to": 0.7}]))
    b = scene(actor(x=-0.8, pose="think", expression="sad", continue_from_previous=True))
    r = renderer([a, b])
    before = r.scenes[0].chars[0]
    after = r.scenes[1].chars[0]
    assert abs(after.x_at(0.0)[0] - 0.7) < 1e-6
    assert after.facing_keys[0][1] == 1
    assert after.pose_track(0) == before.pose_track(3.0)
    assert after.expr_track(0) == before.expr_track(3.0)
    assert after.pose_track(0.40) != before.pose_track(3.0)


def test_continuity_never_hijacks_legacy_or_explicit_entry():
    first = scene(actor(x=0.1))
    second = scene(actor(x=-0.7))
    old = renderer([first, second])
    assert old.scenes[1].chars[0].x_at(0)[0] == -0.7
    entered = renderer([first, scene(actor(x=-0.7, enter="left",
                                           continue_from_previous=True))])
    assert entered.scenes[1].chars[0].x_at(0)[0] < -1.0


def test_follow_camera_tracks_character_and_ignores_absent_characters():
    ch = actor(actions=[{"at": 0.0, "move_to": 0.6}])
    moving = renderer([scene(ch, camera="follow")])
    static = renderer([scene(ch, camera="static")])
    f, s = moving.scenes[0], static.scenes[0]
    assert f.follow_id == "nora"
    assert moving._camera_values(f, 0.0)["x"] < 0.0
    assert moving._camera_values(f, 1.0)["x"] > 0.0
    assert static._camera_values(s, 0.0)["x"] == 0.0
    assert static._camera_values(s, 1.0)["x"] == 0.0
    nobody = renderer([{"narration": "Solo fondo.", "camera": "follow"}])
    assert nobody.scenes[0].follow_id is None
    assert nobody._camera_values(nobody.scenes[0], 1.0)["x"] == 0.0


def test_fade_is_opt_in_and_ends_after_350ms(tmp_path):
    actor_still = actor()
    plain = renderer([scene(actor_still)])
    faded = renderer([scene(actor_still, transition="fade_from_black")])
    pa = tmp_path / "plain.png"
    pb = tmp_path / "fade.png"
    plain.snapshot(0, str(pa))
    faded.snapshot(0, str(pb))
    assert hashlib.sha256(pa.read_bytes()).digest() != hashlib.sha256(pb.read_bytes()).digest()
    plain.snapshot(18, str(pa))
    faded.snapshot(18, str(pb))
    assert hashlib.sha256(pa.read_bytes()).digest() == hashlib.sha256(pb.read_bytes()).digest()


def test_continuity_does_not_change_cast_design():
    r = renderer([scene(actor()), scene(actor(continue_from_previous=True))])
    original_look = r.scenes[0].chars[0].painter.look
    new_look = r.scenes[1].chars[0].painter.look
    assert original_look.color == new_look.color
    assert original_look.hair == new_look.hair == "ponytail"
