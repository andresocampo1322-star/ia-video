"""Planificación narrativa opcional con un LLM local Ollama.

No hace inferencia neuronal por sí mismo: requiere servidor/modelo local.
No envía guiones a ningún servidor externo.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .core import Character, stable_seed, slug


def _loopback(endpoint: str) -> str:
    u = urlsplit(endpoint)
    if u.scheme != "http" or u.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Solo se permite Ollama local mediante http://127.0.0.1 o localhost")
    if u.username or u.password or u.query or u.fragment:
        raise ValueError("URL de Ollama inválida")
    return endpoint.rstrip("/")


def interpret_with_ollama(text: str, *, model: str, endpoint: str = "http://127.0.0.1:11434",
                          timeout: float = 150.0) -> tuple[list[dict], list[Character]]:
    """Devuelve planos y reparto. No genera imágenes ni clips."""
    if not model or not model.strip():
        raise ValueError("Debes indicar un modelo local de Ollama")
    endpoint = _loopback(endpoint)
    instruction = (
        "Eres director de una producción audiovisual. Convierte el libreto en un "
        "JSON estrictamente válido con dos campos: characters y shots. "
        "characters es lista de objetos: name, appearance, clothing, distinctive_features. "
        "Mantén el nombre y aspecto de cada personaje en todo el relato; extrae "
        "sus características del texto y propone detalles SOLO si no se indican. "
        "shots es lista de hasta 36 objetos con text, location, camera, characters, "
        "duration_seconds. Los personajes del campo characters son NOMBRES que también "
        "figuran en la lista de reparto. Camera debe ser medium, wide, close_up, "
        "tracking, over_shoulder o low_angle. Duración de 2 a 12 segundos. "
        "No inventes acciones narrativas ni cambies el orden de acontecimientos. "
        "Las escenas de acción deben separarse en planos visualmente realizables. "
        "No agregues instrucciones fuera del JSON."
    )
    body = {
        "model": model, "stream": False, "format": "json",
        "options": {"temperature": 0.2},
        "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": text[:100000]},
        ],
    }
    request = Request(endpoint + "/api/chat", method="POST",
                      data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except OSError as exc:
        raise RuntimeError(f"No se pudo consultar Ollama local: {exc}") from exc
    raw = data.get("message", {}).get("content", "")
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("El modelo local no devolvió JSON válido") from exc
    if not isinstance(parsed, dict):
        raise ValueError("La respuesta del LLM debe ser un objeto")
    shots = parsed.get("shots")
    people = parsed.get("characters", [])
    if not isinstance(shots, list) or not 1 <= len(shots) <= 36:
        raise ValueError("El LLM debe devolver entre 1 y 36 planos")
    if not isinstance(people, list):
        raise ValueError("characters debe ser una lista")
    cast = []
    seen = set()
    for item in people[:24]:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        name = str(item["name"]).strip()
        key = slug(name)
        if key in seen:
            continue
        seen.add(key)
        cast.append(Character(id=key, name=name,
                              appearance=str(item.get("appearance", ""))[:500],
                              clothing=str(item.get("clothing", ""))[:400],
                              distinctive_features=str(item.get("distinctive_features", ""))[:400],
                              seed=stable_seed(key, name)))
    result = []
    for i, shot in enumerate(shots):
        if not isinstance(shot, dict) or not str(shot.get("text", "")).strip():
            raise ValueError(f"Plano {i + 1}: incompleto")
        participants = shot.get("characters", [])
        if not isinstance(participants, list):
            participants = []
        duration = shot.get("duration_seconds", 5)
        try:
            duration = float(duration)
        except (ValueError, TypeError):
            duration = 5.0
        result.append({
            "text": str(shot["text"])[:1800],
            "location": str(shot.get("location", "unspecified"))[:100],
            "camera": str(shot.get("camera", "medium"))[:60],
            "characters": [str(n)[:80] for n in participants],
            "duration_seconds": duration,
        })
    return result, cast
