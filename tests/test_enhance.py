"""Regresiones del modo de mejora automática, aislado del flujo legado."""
import json

from stickman.enhance import enhance_script
from stickman.schema import validate_script


def script():
    raw = {
        "title": "Personaje continuo",
        "cast": [{"id": "nora"}],
        "scenes": [
            {"id": "a", "narration": "Nora camina.",
             "background": "cielo", "camera": "static",
             "characters": [{"id": "nora", "x": -0.7, "pose": "wave",
                             "actions": [{"at": 0.0, "move_to": 0.7}]}]},
            {"id": "b", "narration": "Nora camina otra vez.",
             "background": "cielo", "camera": "static",
             "characters": [{"id": "nora", "x": -0.7, "pose": "think",
                             "actions": [{"at": 0.1, "move_to": 0.1}]}]},
            {"id": "c", "narration": "Cambia el escenario.",
             "background": "noche", "camera": "zoom_in",
             "characters": [{"id": "nora", "x": 0.1, "pose": "sad"}]},
        ],
    }
    validated, warnings = validate_script(raw)
    assert not warnings
    return validated


def test_enhancement_returns_copy_without_mutating_original():
    original = script()
    before = original.to_json()
    enhanced = enhance_script(original)
    assert original.to_json() == before
    assert enhanced is not original
    assert enhanced.scenes[0].characters[0] is not original.scenes[0].characters[0]


def test_cinematic_auto_applies_only_when_safe():
    enhanced = enhance_script(script())
    s1, s2, s3 = enhanced.scenes
    assert s1.camera == "follow"
    assert s1.characters[0].movement_ease == "ease_in_out"
    assert not s1.characters[0].continue_from_previous
    assert s2.camera == "follow"
    assert s2.characters[0].continue_from_previous
    assert s2.characters[0].movement_ease == "ease_in_out"
    assert s3.camera == "zoom_in"
    assert not s3.characters[0].continue_from_previous
    assert s3.characters[0].movement_ease == "linear"


def test_explicit_entry_and_exit_disable_continuity():
    s = script()
    s.scenes[0].characters[0].exit = "left"
    out = enhance_script(s)
    assert out.scenes[1].characters[0].continue_from_previous is False
    s.scenes[0].characters[0].exit = "none"
    s.scenes[1].characters[0].enter = "right"
    assert enhance_script(s).scenes[1].characters[0].continue_from_previous is False


def test_does_not_change_multi_character_or_manual_camera():
    s = script()
    s.scenes[0].characters.append(
        type(s.scenes[0].characters[0])(id="secundario", x=0.2))
    out = enhance_script(s)
    assert out.scenes[0].camera == "static"
    assert out.scenes[2].camera == "zoom_in"


def test_enhancement_is_idempotent():
    once = enhance_script(script())
    twice = enhance_script(once)
    assert once.to_json() == twice.to_json()


def test_web_render_field_is_off_by_default_and_ui_is_opt_in():
    from pathlib import Path
    from stickman.web.app import RenderIn

    assert RenderIn(script={}).animacion_mejorada is False
    assert RenderIn(script={}, animacion_mejorada=True).animacion_mejorada is True
    html = (Path(__file__).resolve().parents[1] / "stickman" / "web" /
            "static" / "index.html").read_text(encoding="utf-8")
    assert 'id="animacion-mejorada"' in html
    assert "animacion_mejorada: $('animacion-mejorada').checked" in html


def test_cli_option_forwards_enhanced_script(monkeypatch, tmp_path):
    from stickman.cli import main
    from stickman import pipeline

    data = json.loads(script().to_json())
    path = tmp_path / "guion.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    received = []

    def fake_render(script_arg, *args, **kw):
        received.append(script_arg)
        return {"mp4": "prueba.mp4", "srt": "prueba.srt", "stats": kw["stats"]}

    monkeypatch.setattr(pipeline, "render_script", fake_render)
    assert main(["--guion", str(path), "--salida", str(tmp_path / "out1")]) == 0
    assert main(["--guion", str(path), "--animacion-mejorada",
                 "--salida", str(tmp_path / "out2")]) == 0
    assert received[0].scenes[0].camera == "static"
    assert received[1].scenes[0].camera == "follow"
