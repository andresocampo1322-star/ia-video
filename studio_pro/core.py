"""Biblia visual y planificación de planos para producción de anime.

El analizador sin LLM es un respaldo *heurístico*, no una interpretación
semántica humana. Con Ollama disponible se puede usar el planificador LLM.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STYLE_GUIDES = {
    "manga_monochrome": {
        "positive": ("highly detailed monochrome anime film, inked manga line art, "
                     "controlled grayscale tonal values, coherent 2D character design, "
                     "fine architectural perspective, realistic props, cinematic composition, "
                     "soft ambient occlusion, accurate hands, richly detailed urban environments"),
        "negative": ("stick figures, simple geometric bodies, low-detail flat background, "
                     "inconsistent face, inconsistent clothing, additional limbs, "
                     "unwanted text, low resolution, flicker, warped architecture"),
    },
    "anime_color": {
        "positive": ("high-quality hand-drawn anime film, consistent character model sheet, "
                     "rich color scripting, detailed background painting, soft cinematic light, "
                     "expressive animation poses, perspective-correct environment"),
        "negative": "off-model faces, flat lighting, low-detail backgrounds, extra fingers, flicker",
    },
    "stylized_3d": {
        "positive": ("expressive stylized 3D animated film, sculpted materials, physically plausible "
                     "lighting, coherent character topology, refined cloth and hair, cinematic staging"),
        "negative": "untextured models, broken joints, inconsistent costume, clipping, jitter",
    },
    "cinematic_realism": {
        "positive": ("cinematic photorealistic live-action shot, natural anatomy and motion, "
                     "high-detail production design, professional lighting, lens-consistent depth"),
        "negative": "cartoon, plastic skin, waxy faces, distorted anatomy, temporally unstable objects",
    },
}

LOCATIONS = {
    "supermarket": ("supermercado", "tienda de comestibles", "mercado", "grocery store"),
    "street": ("calle", "avenida", "acera", "barrio", "avenue", "street"),
    "room": ("habitación", "cuarto", "apartamento", "dormitorio", "bedroom", "room"),
    "forest": ("bosque", "selva", "forest", "woods"),
    "school": ("escuela", "colegio", "salón de clases", "classroom"),
    "hospital": ("hospital", "clínica", "emergencias"),
    "office": ("oficina", "despacho", "office"),
}
SUBJECT_VERBS = ("camina", "corre", "entra", "sale", "mira", "escucha", "sostiene",
                 "abre", "encuentra", "grita", "ve", "salta", "despierta", "observa",
                 "se acerca", "se detiene", "está", "toma", "habla", "llega", "huye")
RESERVED = {"El", "La", "Los", "Las", "Un", "Una", "En", "A", "Al", "De",
            "Del", "Por", "Con", "Sin", "Entonces", "Luego", "Mientras",
            "Después", "Cuando", "Finalmente", "Frente", "Pero", "Dentro",
            "Mira", "Escena", "Exterior", "Interior", "Noche", "Día"}
CAMS = {
    "close_up": ("rostro", "primer plano", "ojos", "expresión", "susurra", "close-up"),
    "tracking": ("corre", "camina", "persigue", "huye", "avanza", "recorre"),
    "wide": ("calle", "ciudad", "edificio", "paisaje", "panorámica", "supermercado"),
}


def slug(value: str) -> str:
    raw = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", raw).strip("_")[:48] or "character"


def stable_seed(*parts: str) -> int:
    data = "|".join(parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(data).digest()[:4], "big")


@dataclass
class Character:
    id: str
    name: str
    appearance: str = ""
    clothing: str = ""
    distinctive_features: str = ""
    reference_image: str | None = None
    seed: int = 0

    def anchor(self) -> str:
        parts = [f"Character {self.name} (identity {self.id})"]
        for field_name in ("appearance", "clothing", "distinctive_features"):
            detail = getattr(self, field_name)
            if detail:
                parts.append(detail)
        parts.append("same face, hair, clothing and proportions across every shot")
        return "; ".join(parts)


@dataclass
class Shot:
    id: str
    text: str
    location: str
    camera: str
    characters: list[str]
    duration_seconds: float
    seed: int
    prompt: str = ""
    negative_prompt: str = ""
    reference_images: list[str] = field(default_factory=list)


@dataclass
class Project:
    title: str
    style: str
    aspect_ratio: str
    source_text: str
    characters: list[Character]
    shots: list[Shot]
    interpreter: str = "heuristic"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, directory: str | Path) -> Path:
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        target = out / "production_plan.json"
        target.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
                          encoding="utf-8")
        for shot in self.shots:
            (out / f"{shot.id}_prompt.txt").write_text(
                shot.prompt + "\n\nNEGATIVE:\n" + shot.negative_prompt + "\n",
                encoding="utf-8")
        return target


def split_script(text: str) -> list[str]:
    text = text.strip()
    if not text:
        raise ValueError("El libreto está vacío")
    if len(text) > 100_000:
        raise ValueError("Máximo 100 000 caracteres por proyecto")
    segments = [re.sub(r"\s+", " ", s).strip() for s in
                re.split(r"\n\s*\n|(?im)^\s*(?:ESCENA|SCENE)\s*\d+\s*[:.-]\s*", text)]
    segments = [s for s in segments if s]
    if len(segments) == 1 and len(text) > 700:
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ])", text)
        segments, chunk = [], []
        for sentence in sentences:
            if sum(len(part) for part in chunk) + len(sentence) > 520 and chunk:
                segments.append(" ".join(chunk))
                chunk = []
            chunk.append(sentence)
        if chunk:
            segments.append(" ".join(chunk))
    return segments[:36]


def discover_names(text: str) -> list[str]:
    """Heurística transparente: nombres al inicio de frase seguidos de un verbo."""
    names: list[str] = []
    verbs = "|".join(re.escape(v) for v in SUBJECT_VERBS)
    pat = re.compile(r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})\s+(?:" + verbs + r")\b", re.I)
    for m in pat.finditer(text):
        name = m.group(1)
        if name not in RESERVED and name not in names:
            names.append(name)
    return names[:8]


def choose_location(text: str, fallback: str = "unspecified") -> str:
    lower = text.casefold()
    for key, variants in LOCATIONS.items():
        if any(v in lower for v in variants):
            return key
    return fallback


def choose_camera(text: str) -> str:
    lower = text.casefold()
    for key, variants in CAMS.items():
        if any(v in lower for v in variants):
            return key
    return "medium"


def load_cast(path: str | Path) -> list[Character]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw.get("characters") if isinstance(raw, dict) else raw
    if not isinstance(items, list) or not items:
        raise ValueError("El archivo de reparto necesita una lista 'characters'")
    chars = []
    used = set()
    for item in items:
        if not isinstance(item, dict) or not item.get("name"):
            raise ValueError("Cada personaje necesita 'name'")
        name = str(item["name"]).strip()
        key = slug(str(item.get("id", name)))
        if key in used:
            raise ValueError(f"Identidad duplicada: {key}")
        used.add(key)
        chars.append(Character(id=key, name=name,
                               appearance=str(item.get("appearance", "")),
                               clothing=str(item.get("clothing", "")),
                               distinctive_features=str(item.get("distinctive_features", "")),
                               reference_image=item.get("reference_image"),
                               seed=stable_seed(key, name)))
    return chars


def make_project(text: str, *, title: str = "Nuevo episodio",
                 style: str = "manga_monochrome", aspect_ratio: str = "9:16",
                 cast: list[Character] | None = None,
                 interpreted: list[dict[str, Any]] | None = None) -> Project:
    if style not in STYLE_GUIDES:
        raise ValueError(f"Estilo no disponible: {style}")
    if aspect_ratio not in ("9:16", "16:9", "1:1"):
        raise ValueError("Formato admitido: 9:16, 16:9, 1:1")
    fragments = split_script(text)
    known = list(cast) if cast is not None else [
        Character(id=slug(n), name=n, seed=stable_seed(n)) for n in discover_names(text)]
    warnings = []
    if not known:
        warnings.append("No hay reparto identificado: define characters.json para fijar las identidades.")
    if any(not c.appearance or not c.reference_image for c in known):
        warnings.append("Faltan descripciones o imágenes maestras en parte del reparto; "
                        "no se puede garantizar consistencia de rostros sin referencias.")
    records = interpreted if interpreted is not None else [
        {"text": fragment, "location": choose_location(fragment),
         "camera": choose_camera(fragment), "duration_seconds": 5.0}
        for fragment in fragments]
    if not isinstance(records, list) or not records or len(records) > 36:
        raise ValueError("El plan debe tener entre 1 y 36 planos")
    shots = []
    guide = STYLE_GUIDES[style]
    active_location = "unspecified"
    for idx, item in enumerate(records, start=1):
        spoken = str(item.get("text", "")).strip()
        if not spoken:
            raise ValueError(f"Plano {idx}: texto vacío")
        location = str(item.get("location") or choose_location(spoken, active_location))
        if location == "unspecified":
            location = active_location
        if location != "unspecified":
            active_location = location
        camera = str(item.get("camera") or choose_camera(spoken))
        if camera not in ("medium", "wide", "close_up", "tracking", "over_shoulder", "low_angle"):
            camera = "medium"
        duration = max(2.0, min(12.0, float(item.get("duration_seconds", 5.0))))
        names_in_shot = [c for c in known if re.search(r"\b" + re.escape(c.name) + r"\b",
                                                       spoken, re.I)]
        ids_requested = item.get("characters")
        if isinstance(ids_requested, list):
            names_in_shot = [c for c in known if c.id in ids_requested or c.name in ids_requested]
        anchors = [c.anchor() for c in names_in_shot]
        ref_images = [c.reference_image for c in names_in_shot if c.reference_image]
        prompt = ("STYLE: " + guide["positive"] +
                  ". FORMAT: " + aspect_ratio + ". CAMERA: " + camera +
                  ". LOCATION: " + location +
                  ". ACTION: " + spoken +
                  (". CHARACTER BIBLE: " + " | ".join(anchors) if anchors else "") +
                  ". Preserve spatial continuity and light direction, maintain stable design.")
        shot = Shot(id=f"shot_{idx:03d}", text=spoken, location=location,
                    camera=camera, characters=[c.id for c in names_in_shot],
                    duration_seconds=duration, seed=stable_seed(title, style, str(idx)),
                    prompt=prompt, negative_prompt=guide["negative"],
                    reference_images=ref_images)
        shots.append(shot)
    return Project(title=title, style=style, aspect_ratio=aspect_ratio,
                   source_text=text, characters=known, shots=shots,
                   interpreter="llm" if interpreted is not None else "heuristic",
                   warnings=warnings)
