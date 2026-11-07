"""Pruebas de motor Stickman IA clásico sin ComfyUI y sin sustituir el renderer."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from studio_pro.original import build_original_script, render_original


ROOT = Path(__file__).resolve().parents[1]
STORY = ROOT / "examples" / "la_vecina" / "historia.txt"
CAST = ROOT / "examples" / "la_vecina" / "personajes.json"


def test_story_builds_12_scenes_and_two_persistent_identities():
    script = build_original_script(STORY.read_text(encoding="utf-8"),
                                   cast_file=CAST, title="La vecina")
    assert script.title == "La vecina"
    assert len(script.scenes) == 12
    assert len(script.cast) == 2
    assert [m.id for m in script.cast] == ["alex", "vecina"]
    assert script.cast[0].preset.hair == "long"
    assert script.cast[1].preset.color == "#A9A8A1"
    assert all(1 <= len(sc.characters) <= 3 for sc in script.scenes)


def test_story_contains_television_attack_chase_and_fence_leap():
    script = build_original_script(STORY.read_text(encoding="utf-8"), cast_file=CAST)
    assert script.scenes[0].environment == "room"
    assert any("ALERTA DE EMERGENCIA" in k.text for k in script.scenes[0].keywords)
    assert any("ALERTA DE EMERGENCIA" in k.text for k in script.scenes[1].keywords)
    assert any("ALGO NO ESTÁ BIEN" in k.text for k in script.scenes[6].keywords)
    assert any(c.pose == "stagger" or c.gait == "sneak"
               for s in script.scenes for c in s.characters if c.id == "vecina")
    assert any(a.pose == "attack" for s in script.scenes
               for c in s.characters if c.id == "vecina" for a in c.actions)
    assert any(a.pose == "jump" for s in script.scenes
               for c in s.characters if c.id == "alex" for a in c.actions)
    assert script.scenes[-1].environment == "street"


def test_validation_without_comfy_creates_json_not_fake_mp4(tmp_path):
    result = render_original(
        STORY.read_text(encoding="utf-8"), tmp_path,
        cast_file=CAST, execute=False)
    assert result["status"] == "validated"
    assert result["engine"] == "stickman_original"
    script = Path(result["script"])
    assert script.is_file()
    assert len(json.loads(script.read_text(encoding="utf-8"))["scenes"]) == 12
    assert not list(tmp_path.glob("*.mp4"))


def test_generic_story_from_plain_text_works_without_cast():
    txt = ("Lina camina por una calle oscura.\n\n"
           "Lina corre, salta una cerca y escapa del peligro.")
    script = build_original_script(txt)
    assert len(script.scenes) == 2
    assert script.cast[0].name == "Lina"
    assert script.scenes[1].environment == "street"
    assert script.scenes[1].characters[0].gait == "run"


def test_renderer_keeps_original_pipeline_and_checks_mp4(monkeypatch, tmp_path):
    from stickman import pipeline
    inputs = {}

    def fake_render(script, out, *args, **kwargs):
        inputs["script"] = script
        inputs["args"] = args
        inputs["kwargs"] = kwargs
        p = Path(out) / "episodio_stickman.mp4"
        p.write_bytes(bytes(5000))
        return {"mp4": str(p), "duration": 4.0}

    monkeypatch.setattr(pipeline, "render_script", fake_render)
    result = render_original("Álex camina por la calle.", tmp_path,
                             cast_file=CAST, execute=True)
    assert result["status"] == "completed"
    assert Path(result["mp4"]).is_file()
    assert inputs["kwargs"]["basename"] == "episodio_stickman"
    assert inputs["kwargs"]["word_align"] is False
    assert inputs["kwargs"]["fmt"] == "9:16"
    assert inputs["kwargs"]["engine"] == "piper"


def test_no_success_if_renderer_did_not_create_mp4(monkeypatch, tmp_path):
    from stickman import pipeline

    monkeypatch.setattr(pipeline, "render_script", lambda *a, **k: {
        "mp4": str(tmp_path / "missing.mp4"), "duration": 4.0})
    with pytest.raises(RuntimeError, match="sin producir un MP4"):
        render_original("Álex camina.", tmp_path, cast_file=CAST, execute=True)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_genuine_original_skia_renderer_outputs_video(tmp_path):
    from stickman.audio import SR, write_wav
    from stickman.render import VideoRenderer

    raw = ("Álex mira la televisión.\n\n"
           "Álex corre hacia una cerca y salta para escapar.")
    script = build_original_script(raw, cast_file=CAST)
    durations, fps = [2.3, 2.4], 12
    renderer = VideoRenderer(
        script, "9:16", durations,
        np.zeros(round(sum(durations) * fps), np.float32), [],
        fps=fps, render_scale=0.40)
    wav = tmp_path / "silent.wav"
    write_wav(wav, np.zeros(round(sum(durations) * SR), np.float32))
    mp4 = tmp_path / "real_skia.mp4"
    renderer.render(str(mp4), str(wav))
    assert mp4.stat().st_size > 2500
    assert mp4.read_bytes()[4:8] == b"ftyp"
