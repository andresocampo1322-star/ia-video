"""Nuevas poses: registro, rig intacto, animación mediante Track original."""
import math

import numpy as np

from stickman.rig.poses import POSES, get_pose
from stickman.rig.skeleton import BONES, forward
from stickman.render import VideoRenderer
from stickman.schema import POSES as SCHEMA_POSES, validate_script

NEW = ("crouch", "cower", "stagger", "attack", "reach", "guard")


def test_all_new_poses_are_registered_and_nontrivial():
    for name in NEW:
        assert name in POSES and name in SCHEMA_POSES
        joints = get_pose(name)
        assert joints.keys() == get_pose("idle").keys()
        assert joints != get_pose("idle")
        assert all(math.isfinite(x) for x in joints.values())


def test_original_poses_are_untouched():
    assert get_pose("idle")["spine"] == -90.0
    assert get_pose("wave")["r_sh"] == -28
    assert get_pose("point")["r_sh"] == -12
    assert get_pose("sit")["l_knee"] == 92


def test_all_new_poses_obey_rig_fixed_bones():
    for name in NEW:
        pts = forward(get_pose(name))
        for side in ("l", "r"):
            assert abs(math.dist(pts[f"{side}_shoulder"],
                                 pts[f"{side}_elbow"]) - BONES["upper_arm"]) < 1e-6
            assert abs(math.dist(pts[f"{side}_elbow"],
                                 pts[f"{side}_wrist"]) - BONES["forearm"]) < 1e-6
            assert abs(math.dist(pts["hip"], pts[f"{side}_knee"]) - BONES["thigh"]) < 1e-6
            assert abs(math.dist(pts[f"{side}_knee"],
                                 pts[f"{side}_ankle"]) - BONES["shin"]) < 1e-6


def test_pose_aliases_and_manual_actions():
    raw = {"title": "poses", "cast": [{"id": "nora"}],
           "scenes": [{"narration": "Protege tu cabeza.",
                       "characters": [{"id": "nora", "pose": "scared",
                                       "actions": [{"at": 0.2, "pose": "attacking"}]}]}]}
    script, warnings = validate_script(raw)
    assert not warnings
    ch = script.scenes[0].characters[0]
    assert ch.pose == "cower"
    assert ch.actions[0].pose == "attack"


def test_new_poses_render_with_original_engine(tmp_path):
    for pose in NEW:
        script, warnings = validate_script({
            "title": "pose", "cast": [{"id": "a"}],
            "scenes": [{"narration": "Escena simple.",
                        "characters": [{"id": "a", "pose": pose}]}]})
        assert not warnings
        renderer = VideoRenderer(script, "16:9", [1.0],
                                 np.zeros(30, np.float32), [],
                                 fps=30, render_scale=0.4)
        img = tmp_path / (pose + ".png")
        renderer.snapshot(0, str(img))
        assert img.stat().st_size > 1000


def test_existing_track_blends_to_new_pose_without_jump():
    script, _ = validate_script({
        "title": "pose", "cast": [{"id": "a"}],
        "scenes": [{"narration": "Un gesto nuevo.",
                    "characters": [{"id": "a", "pose": "idle",
                                    "actions": [{"at": 0.25, "pose": "cower"}]}]}]})
    renderer = VideoRenderer(script, "16:9", [2.0],
                             np.zeros(60, np.float32), [], fps=30)
    track = renderer.scenes[0].chars[0].pose_track
    prev = track(0.5)
    nxt = track(0.5001)
    assert max(abs(nxt[k] - prev[k]) for k in prev) < 0.5
    assert track(1.2) == get_pose("cower")
