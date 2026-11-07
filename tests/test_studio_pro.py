"""Pruebas sin GPU, sin Ollama, sin ComfyUI y sin servicios externos."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from studio_pro.cli import main
from studio_pro.comfy import (ComfyClient, bind_workflow, dimensions, load_api_workflow,
                              load_bindings, local_url)
from studio_pro.core import (Character, Shot, choose_camera, choose_location, discover_names,
                             load_cast, make_project, slug, split_script, stable_seed)
from studio_pro.ollama import interpret_with_ollama
from studio_pro.skills import SKILLS, get_skills, validate_skill_graph


STORY = (
    "Nora camina por una calle silenciosa.\n\n"
    "Nora entra al supermercado. Escucha gritos y observa personas corriendo."
)
CAST = [Character(id="nora", name="Nora",
                  appearance="cabello negro corto, ojos oscuros",
                  clothing="sudadera oscura y pantalones negros",
                  reference_image="nora_ref.png",
                  seed=101)]


def test_reference_style_is_high_detail_not_stickman():
    project = make_project(STORY, cast=CAST)
    assert project.style == "manga_monochrome"
    assert "monochrome anime film" in project.shots[0].prompt
    assert "stick figures" in project.shots[0].negative_prompt
    assert "cabello negro corto" in project.shots[0].prompt


def test_character_identity_is_stable_across_shots_and_seeds():
    one = make_project(STORY, cast=CAST, title="Episodio 1")
    two = make_project(STORY, cast=CAST, title="Episodio 1")
    assert [s.seed for s in one.shots] == [s.seed for s in two.shots]
    assert one.shots[0].characters == ["nora"]
    assert one.shots[1].characters == ["nora"]
    assert one.shots[0].reference_images == one.shots[1].reference_images == ["nora_ref.png"]
    assert "same face, hair, clothing" in one.shots[1].prompt


def test_planner_does_not_falsely_claim_video_generated(tmp_path):
    project = make_project(STORY, cast=CAST)
    file = project.save(tmp_path)
    assert file.name == "production_plan.json"
    data = json.loads(file.read_text(encoding="utf-8"))
    assert len(data["shots"]) == 2
    assert (tmp_path / "shot_001_prompt.txt").exists()
    assert not list(tmp_path.glob("*.mp4"))


def test_character_design_variants_supported():
    alice = Character(id="nora", name="Nora", appearance="trenzas rojas",
                      clothing="chaqueta amarilla")
    bob = Character(id="leo", name="Leo", appearance="cabello blanco",
                    clothing="gabardina azul")
    project = make_project("Nora camina.\n\nLeo corre.", cast=[alice, bob])
    assert project.shots[0].characters == ["nora"]
    assert project.shots[1].characters == ["leo"]
    assert "trenzas rojas" in project.shots[0].prompt
    assert "cabello blanco" in project.shots[1].prompt
    assert "gabardina azul" not in project.shots[0].prompt


def test_script_empty_and_validations():
    with pytest.raises(ValueError, match="vacío"):
        split_script("  ")
    with pytest.raises(ValueError):
        make_project(STORY, style="pretend_model")
    with pytest.raises(ValueError):
        make_project(STORY, aspect_ratio="4:1")
    assert choose_location("Entró al supermercado") == "supermarket"
    assert choose_camera("La cámara muestra su rostro") == "close_up"
    assert stable_seed("nora") == stable_seed("nora")
    assert slug("Ñora de Málaga") == "nora_de_malaga"


def test_cast_validation_and_duplicates(tmp_path):
    good = tmp_path / "cast.json"
    good.write_text(json.dumps({"characters": [
        {"name": "Nora", "appearance": "rizo negro", "reference_image": "nora.png"},
        {"name": "Leo", "clothing": "abrigo"}]}))
    assert [c.id for c in load_cast(good)] == ["nora", "leo"]
    good.write_text(json.dumps([{"name": "Nora"}, {"name": "Nora"}]))
    with pytest.raises(ValueError, match="duplicada"):
        load_cast(good)


def test_discover_names_does_not_force_character_description():
    assert "Nora" in discover_names("Nora camina hacia la calle.")
    project = make_project("Una calle desierta.")
    assert project.warnings
    assert not project.characters


def test_skills_registry_distinguishes_implemented_and_aspirational():
    validate_skill_graph()
    statuses = {s["id"]: s["status"] for s in get_skills()}
    assert statuses["shot.prompt"] == "implemented"
    assert statuses["video.identity_consistency"] == "not_implemented"
    assert len(SKILLS) >= 12


def test_comfyui_workflow_patching_preserves_original():
    graph = {"6": {"class_type": "CLIPTextEncode", "inputs": {"text": "BEFORE"}},
             "7": {"class_type": "KSampler", "inputs": {"seed": 0}},
             "8": {"class_type": "EmptyLatentImage",
                   "inputs": {"width": 512, "height": 512, "batch_size": 1}}}
    bindings = {"positive_prompt": {"node": "6", "input": "text"},
                "seed": {"node": "7", "input": "seed"},
                "width": {"node": "8", "input": "width"},
                "height": {"node": "8", "input": "height"}}
    shot = make_project(STORY, cast=CAST).shots[0]
    patched = bind_workflow(graph, bindings, shot, "9:16")
    assert graph["6"]["inputs"]["text"] == "BEFORE"
    assert patched["6"]["inputs"]["text"] == shot.prompt
    assert patched["7"]["inputs"]["seed"] == shot.seed
    assert patched["8"]["inputs"]["width"] == 720
    assert patched["8"]["inputs"]["height"] == 1280


def test_workflow_rejects_wrong_node_field_link_or_reference():
    graph = {"6": {"class_type": "Text", "inputs": {"text": ["1", 0]}}}
    shot = make_project(STORY, cast=CAST).shots[0]
    with pytest.raises(ValueError, match="enlace"):
        bind_workflow(graph, {"positive_prompt": {"node": "6", "input": "text"}}, shot)
    with pytest.raises(ValueError, match="nodo"):
        bind_workflow(graph, {"positive_prompt": {"node": "8", "input": "text"}}, shot)
    graph["6"]["inputs"]["text"] = "start"
    with pytest.raises(ValueError, match="referencia"):
        bind_workflow(graph, {"positive_prompt": {"node": "6", "input": "text"},
                              "reference_image": {"node": "6", "input": "text"}}, shot)


def test_load_workflow_rejects_visual_node_graph(tmp_path):
    f = tmp_path / "graph.json"
    f.write_text('{"nodes":[{"id":1}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="API"):
        load_api_workflow(f)
    f.write_text('{"6":{"class_type":"CLIPTextEncode","inputs":{"text":"hello"}}}')
    assert load_api_workflow(f)["6"]["inputs"]["text"] == "hello"


def test_load_bindings_rejects_unknown_semantics(tmp_path):
    f = tmp_path / "bindings.json"
    f.write_text(json.dumps({"positive_prompt": {"node": "6", "input": "text"},
                              "magic_invented_node": {"node": "8", "input": "x"}}))
    with pytest.raises(ValueError, match="no soportada"):
        load_bindings(f)


def test_comfyui_never_connects_to_remote_by_default():
    assert local_url("http://127.0.0.1:8188") == "http://127.0.0.1:8188"
    with pytest.raises(ValueError):
        local_url("https://unknown-remote.example.com")
    with pytest.raises(ValueError):
        ComfyClient("http://10.0.0.1:8188")
    assert dimensions("16:9", "720p") == (1280, 720)
    assert dimensions("9:16", "720p") == (720, 1280)


def test_ollama_model_parses_structured_json_without_real_connection(monkeypatch):
    import studio_pro.ollama as m

    example = {"characters": [{"name": "Nora", "appearance": "cabello negro",
                                "clothing": "sudadera negra"}],
               "shots": [{"text": "Nora abre la puerta.",
                          "location": "supermarket", "camera": "wide",
                          "characters": ["Nora"], "duration_seconds": 5}]}
    result = {"message": {"content": json.dumps(example)}}

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def read(self):
            return json.dumps(result).encode()

    def fake_open(request, timeout):
        assert request.full_url == "http://127.0.0.1:11434/api/chat"
        return FakeResponse()

    monkeypatch.setattr(m, "urlopen", fake_open)
    scenes, people = interpret_with_ollama("Nora abre la puerta.", model="test-local")
    assert scenes[0]["characters"] == ["Nora"]
    assert people[0].appearance == "cabello negro"
    with pytest.raises(ValueError, match="local"):
        interpret_with_ollama("Text", model="x", endpoint="https://remote.example")


def test_cli_plan_without_gpu_or_api(tmp_path):
    s = tmp_path / "script.txt"
    s.write_text(STORY, encoding="utf-8")
    cast = tmp_path / "cast.json"
    cast.write_text(json.dumps({"characters": [
        {"name": "Nora", "appearance": "cabello negro", "clothing": "sudadera negra"}]}))
    out = tmp_path / "out"
    assert main(["plan", "--script", str(s), "--cast", str(cast),
                 "--out", str(out)]) == 0
    assert (out / "production_plan.json").exists()
    assert not list(out.rglob("*.mp4"))


def test_cli_render_workflow_dry_run_never_uses_network(tmp_path, monkeypatch):
    import studio_pro.cli as cli
    project = make_project(STORY, cast=CAST)
    plan = project.save(tmp_path / "project")
    graph = tmp_path / "wf.json"
    graph.write_text('{"6":{"class_type":"CLIPTextEncode","inputs":{"text":""}}}')
    bindings = tmp_path / "binding.json"
    bindings.write_text('{"positive_prompt":{"node":"6","input":"text"}}')

    def fail(*args, **kwargs):
        raise AssertionError("Dry-run MUST NOT construct HTTP client")

    monkeypatch.setattr(cli, "ComfyClient", fail)
    out = tmp_path / "outputs"
    assert main(["render-project", "--project", str(plan),
                 "--workflow", str(graph), "--bindings", str(bindings),
                 "--out", str(out)]) == 0
    assert len(list(out.glob("shot_*_workflow.json"))) == 2
    assert json.loads((out / "jobs.json").read_text())[0]["status"] == "prepared"
