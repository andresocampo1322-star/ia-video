"""Integración de TODO el orquestador con ComfyUI simulado y FFmpeg real.

Mock NO demuestra calidad visual de modelo neuronal; prueba que las etapas
de referencia, imágenes, video, QC, MP4 y reanudación se encadenan.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import zlib
import struct
from pathlib import Path

import pytest

from studio_pro.cli import main
from studio_pro.comfy import bind_workflow, ComfyClient
from studio_pro.core import make_project
from studio_pro.production import produce
from studio_pro.skills import get_skills

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def png(path: Path) -> None:
    """PNG RGB válido (cuadrado 16x16) construido sin Pillow."""
    def chunk(kind, payload):
        data = kind + payload
        return struct.pack(">I", len(payload)) + data + struct.pack(">I", zlib.crc32(data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x85\x88\x99" * 16 for _ in range(16))
    body = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR",
        struct.pack(">IIBBBBB", 16, 16, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    path.write_bytes(body)


def setup(tmp_path):
    root = tmp_path / "workflows"
    root.mkdir()
    cfg = {
        "version": 1, "title": "Prueba end to end",
        "style": "anime_color", "aspect_ratio": "9:16",
        "fps": 12, "resolution": "540p", "strict_quality": True,
    }
    for stage in ("character", "keyframe", "video"):
        filename = stage + ".json"
        graph = {"1": {"class_type": "CLIPTextEncode",
                       "inputs": {"text": "", "name": stage}},
                 "2": {"class_type": "LoadImage",
                       "inputs": {"image": ""}},
                 "3": {"class_type": "VideoOptions",
                       "inputs": {"frames": 24, "seed": 0}}}
        (root / filename).write_text(json.dumps(graph))
        bindings = {"positive_prompt": {"node": "1", "input": "text"},
                    "seed": {"node": "3", "input": "seed"}}
        if stage == "keyframe":
            bindings["reference_image"] = {"node": "2", "input": "image"}
        if stage == "video":
            bindings["start_frame"] = {"node": "2", "input": "image"}
            bindings["frames"] = {"node": "3", "input": "frames"}
        (root / (stage + "_bindings.json")).write_text(json.dumps(bindings))
        cfg[stage] = {"workflow": filename, "bindings": stage + "_bindings.json"}
    config_path = root / "production.json"
    config_path.write_text(json.dumps(cfg))
    script = tmp_path / "story.txt"
    script.write_text("Nora camina por la calle.\n\nNora entra al supermercado.", encoding="utf-8")
    cast = tmp_path / "cast.json"
    cast.write_text(json.dumps({"characters": [{
        "name": "Nora", "appearance": "pelo negro corto",
        "clothing": "sudadera negra", "reference_image": None}]}))
    return script, cast, config_path


class FakeComfy:
    def __init__(self):
        self.calls = []
        self.graphs = {}
        self.uploads = []

    def health(self):
        return True

    def upload_image(self, path):
        p = Path(path)
        assert p.is_file()
        self.uploads.append(p)
        return f"uploaded_{len(self.uploads)}.png"

    def queue(self, graph):
        stage = graph["1"]["inputs"]["name"]
        self.calls.append(stage)
        ident = f"task_{len(self.calls)}"
        self.graphs[ident] = stage
        if stage == "keyframe":
            assert graph["2"]["inputs"]["image"].startswith("uploaded_")
        if stage == "video":
            assert graph["2"]["inputs"]["image"].startswith("uploaded_")
        return ident

    def wait(self, prompt_id):
        assert prompt_id in self.graphs
        return {"mock_prompt": prompt_id}

    def download_outputs(self, job, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        stage = self.graphs[job["mock_prompt"]]
        if stage == "video":
            out = folder / "generated.mp4"
            subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "lavfi", "-i", "testsrc2=size=288x512:rate=12",
                            "-t", "5.0", "-c:v", "libx264", "-preset", "ultrafast",
                            "-pix_fmt", "yuv420p", str(out)], check=True, timeout=80)
            return [out]
        image = folder / "reference.png"
        png(image)
        return [image]


def test_safe_dry_run_validates_and_does_not_call_gpu(tmp_path):
    script, cast, config = setup(tmp_path)
    output = tmp_path / "episode"
    result = produce(script, cast, config, output, execute=False)
    assert result["executed"] is False
    assert result["shots"] == 2
    assert result["characters"] == 1
    assert (output / "production_plan.json").exists()
    assert not (output / "episodio.mp4").exists()


@pytest.mark.skipif(not (FFMPEG and FFPROBE), reason="FFmpeg required")
def test_one_command_full_pipeline_and_resume(tmp_path):
    script, cast, config = setup(tmp_path)
    out = tmp_path / "episode"
    fake = FakeComfy()
    completed = produce(script, cast, config, out, execute=True, client=fake)
    assert completed["status"] == "completed"
    assert Path(completed["episode"]).stat().st_size > 2000
    assert fake.calls == ["character", "keyframe", "video", "keyframe", "video"]
    data = json.loads((out / "production_state.json").read_text())
    assert data["status"] == "completed" and len(data["shots"]) == 2
    assert all(s["status"] == "completed" for s in data["shots"].values())
    assert all(s["quality"]["technical_ok"] for s in data["shots"].values())
    previous = len(fake.calls)
    again = produce(script, cast, config, out, execute=True, resume=True, client=fake)
    assert again["resumed"] is True
    assert len(fake.calls) == previous
    assert Path(again["episode"]).is_file()


def test_identity_requires_reference_workflow_or_image(tmp_path):
    script, cast, config = setup(tmp_path)
    cfg = json.loads(config.read_text())
    del cfg["character"]
    config.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match="maestras"):
        produce(script, cast, config, tmp_path / "fail", execute=False)


def test_second_character_reference_binding_is_mandatory(tmp_path):
    script, cast, config = setup(tmp_path)
    script.write_text("Nora camina junto a Leo.", encoding="utf-8")
    cast.write_text(json.dumps({"characters": [
        {"name": "Nora", "appearance": "pelo negro", "clothing": "blusa"},
        {"name": "Leo", "appearance": "pelo rubio", "clothing": "camisa"}]}))
    with pytest.raises(ValueError, match="reference_image_2"):
        produce(script, cast, config, tmp_path / "fail", execute=False)


def test_ref_binding_first_frame_and_multiple_character_slots():
    shot = make_project("Nora entra al supermercado.").shots[0]
    graph = {"1": {"class_type": "LoadImage", "inputs": {"image": ""}},
             "2": {"class_type": "LoadImage", "inputs": {"image": ""}},
             "3": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}}}
    bind = {"reference_image": {"node": "1", "input": "image"},
            "reference_image_2": {"node": "2", "input": "image"},
            "positive_prompt": {"node": "3", "input": "text"}}
    result = bind_workflow(graph, bind, shot, reference_images=["nora.png", "leo.png"])
    assert result["1"]["inputs"]["image"] == "nora.png"
    assert result["2"]["inputs"]["image"] == "leo.png"
    assert graph["1"]["inputs"]["image"] == ""


def test_resume_rejects_changed_script(tmp_path):
    script, cast, config = setup(tmp_path)
    out = tmp_path / "episode"
    produce(script, cast, config, out, execute=False)
    script.write_text("Nora vive en el bosque.", encoding="utf-8")
    with pytest.raises(ValueError, match="cambiaron"):
        produce(script, cast, config, out, execute=False, resume=True)


def test_new_skill_is_honest_about_gpu_dependency():
    status = {s["id"]: s["status"] for s in get_skills()}
    assert status["video.identity_consistency"] == "not_implemented"

def test_comfy_upload_image_uses_real_multipart_crlf(monkeypatch, tmp_path):
    import studio_pro.comfy as comfy

    image = tmp_path / "nora.png"
    png(image)
    requests = []

    class MockResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def read(self):
            return json.dumps({"name": "nora_uploaded.png", "subfolder": "", "type": "input"}).encode()

    def fake_open(req, timeout):
        requests.append(req)
        return MockResponse()

    monkeypatch.setattr(comfy, "urlopen", fake_open)
    client = ComfyClient()
    name = client.upload_image(image)
    assert name == "nora_uploaded.png"
    req = requests[0]
    assert req.get_method() == "POST"
    assert req.full_url.endswith("/upload/image")
    body = req.data
    assert body.count(bytes((13, 10))) >= 6
    assert b"Content-Disposition: form-data" in body
    assert b"name=\"image\"" in body
    assert b"nora.png" in body
