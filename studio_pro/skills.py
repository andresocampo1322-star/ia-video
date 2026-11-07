"""Catálogo auditable de capacidades; una skill requiere código y pruebas reales."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Skill:
    id: str
    purpose: str
    status: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    note: str = ""


SKILLS = (
    Skill("script.ingest", "Leer libreto UTF-8 y separar escenas", "implemented",
          ("script_text",), ("scene_fragments",)),
    Skill("cast.bible", "Mantener diseño estable del reparto por identidad", "implemented",
          ("cast.json",), ("character_bible",)),
    Skill("scene.plan", "Interpretar escenas por reglas o modelo de lenguaje", "implemented_limited",
          ("scene_fragments",), ("shot_list",), ("script.ingest",),
          "Heurístico por defecto; semántica avanzada requiere Ollama u otro LLM."),
    Skill("visual.style", "Definir estilo coherente entre escenas", "implemented",
          ("style_id",), ("style_guide",)),
    Skill("shot.prompt", "Construir prompts y referencias por plano", "implemented",
          ("shot_list", "character_bible"), ("shot_prompts",),
          ("scene.plan", "visual.style")),
    Skill("project.export", "Exportar plan reproducible y prompts", "implemented",
          ("shot_prompts",), ("production_plan.json", "shot_XXX_prompt.txt"),
          ("shot.prompt",)),
    Skill("comfy.workflow", "Validar y enlazar nodos de un workflow API de ComfyUI", "implemented",
          ("api_workflow.json", "bindings.json", "shot"), ("bound_workflow",),
          ("shot.prompt",),
          "La generación solo funciona cuando el workflow y modelos están instalados."),
    Skill("comfy.render", "Enviar workflow y recuperar artefactos del servidor local", "implemented_conditional",
          ("bound_workflow", "ComfyUI running"), ("outputs",),
          ("comfy.workflow",)),
    Skill("character.reference_generation", "Crear hojas de modelo multiángulo", "not_implemented",
          ("character_bible",), ("reference_sheet.png",), ("cast.bible",)),
    Skill("character.master_reference", "Generar o reutilizar imagen maestra de cada personaje", "implemented_conditional",
          ("character_bible", "ComfyUI character model"), ("reference_images",),
          ("cast.bible", "comfy.render"),
          "No garantiza la misma identidad sin un modelo de referencia adecuado."),
    Skill("video.first_frame", "Generar fotograma inicial con identidad condicionada", "implemented_conditional",
          ("shot_prompts", "reference_images", "ComfyUI image model"), ("keyframes",),
          ("shot.prompt", "comfy.render")),
    Skill("video.from_image", "Animar fotogramas con modelo I2V real", "implemented_conditional",
          ("keyframes", "ComfyUI video model"), ("shot_videos",),
          ("video.first_frame", "comfy.render")),
    Skill("video.qc_basic", "Revisar duración, formato, negro y movimiento aparente", "implemented",
          ("shot_videos",), ("quality_reports",), ("video.from_image",),
          "No mide anatomía, belleza ni persistencia facial."),
    Skill("audio.piper_narration", "Sintetizar y montar narración con Piper original", "implemented_conditional",
          ("script", "Piper installed"), ("spoken_clips",), ("video.from_image",),
          "No hay lipsync ni voces dramatizadas por personaje."),
    Skill("video.auto_produce", "Orquestar referencias, escenas, video y montaje desde texto", "implemented_conditional",
          ("script", "cast", "ComfyUI workflows configured"), ("episode.mp4",),
          ("video.from_image", "video.qc_basic", "editor.assemble"),
          "Requiere un modelo visual real; no se simula calidad cinematográfica."),
    Skill("video.identity_consistency", "Medir variación de rostro/ropa entre clips", "not_implemented",
          ("generated_frames", "reference_images"), ("consistency_report",)),
    Skill("video.motion_qc", "Detectar flicker y anatomía rota por fotograma", "not_implemented",
          ("generated_video",), ("motion_report",)),
    Skill("audio.lipsync", "Sincronizar fonemas y movimiento de boca", "not_implemented",
          ("speech_audio", "character_track"), ("lip_track",)),
    Skill("editor.assemble", "Montar clips compatibles de la producción generativa", "implemented_basic",
          ("shot_clips",), ("episode.mp4",), (),
          "Montaje FFmpeg de clips compatibles; no sintetiza audio, no realiza lipsync."),
)


def get_skills() -> list[dict]:
    return [asdict(s) for s in SKILLS]


def validate_skill_graph() -> None:
    names = [s.id for s in SKILLS]
    if len(names) != len(set(names)):
        raise ValueError("IDs de skills duplicados")
    by_id = {s.id: s for s in SKILLS}
    for skill in SKILLS:
        for dep in skill.dependencies:
            if dep not in by_id:
                raise ValueError(f"Dependencia no registrada: {dep}")
    visiting, visited = set(), set()

    def dfs(name: str) -> None:
        if name in visiting:
            raise ValueError(f"Ciclo entre skills: {name}")
        if name in visited:
            return
        visiting.add(name)
        for dep in by_id[name].dependencies:
            dfs(dep)
        visiting.remove(name)
        visited.add(name)

    for name in names:
        dfs(name)
