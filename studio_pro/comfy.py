"""Adaptador opcional ComfyUI para flujos API exportados por el usuario.

No crea workflows falsos y nunca genera/cobra si no se solicita la ejecución.
Los nodos y entradas deben indicarse explícitamente en bindings.json.
"""
from __future__ import annotations

import copy
import json
import math
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from .core import Shot

SEMANTIC_FIELDS = frozenset(("positive_prompt", "negative_prompt", "seed",
                             "width", "height", "frames", "reference_image"))


def local_url(endpoint: str) -> str:
    uri = urlsplit(endpoint)
    if uri.scheme != "http" or uri.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("El adaptador solo admite ComfyUI ejecutado en el equipo local")
    if uri.username or uri.password or uri.query or uri.fragment:
        raise ValueError("URL de ComfyUI inválida")
    return endpoint.rstrip("/")


def load_api_workflow(path: str | Path) -> dict:
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(result, dict) or not result:
        raise ValueError("Workflow API JSON vacío")
    if "nodes" in result and isinstance(result["nodes"], list):
        raise ValueError("Exporta el workflow en formato API, no el JSON visual de la interfaz")
    for node_id, node in result.items():
        if not isinstance(node, dict) or not node.get("class_type") or not isinstance(node.get("inputs"), dict):
            raise ValueError(f"Nodo API inválido: {node_id}")
    return result


def load_bindings(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "positive_prompt" not in data:
        raise ValueError("bindings.json debe indicar al menos positive_prompt")
    for semantic, mapping in data.items():
        if semantic not in SEMANTIC_FIELDS:
            raise ValueError(f"Variable de binding no soportada: {semantic}")
        if not isinstance(mapping, dict) or not mapping.get("node") or not mapping.get("input"):
            raise ValueError(f"Binding incompleto: {semantic}")
    return data


def dimensions(aspect_ratio: str, resolution: str = "720p") -> tuple[int, int]:
    base = {"540p": 540, "720p": 720, "1080p": 1080}.get(resolution)
    if base is None:
        raise ValueError("Resolución admitida: 540p, 720p, 1080p")
    formats = {"16:9": (16, 9), "9:16": (9, 16), "1:1": (1, 1)}
    if aspect_ratio not in formats:
        raise ValueError("Formato de imagen no admitido")
    a, b = formats[aspect_ratio]
    w = base if a <= b else round(base * a / b)
    h = base if a >= b else round(base * b / a)
    return 8 * round(w / 8), 8 * round(h / 8)


def bind_workflow(graph: dict, bindings: dict, shot: Shot,
                  aspect_ratio: str = "9:16", resolution: str = "720p",
                  fps: int = 24, reference_filename: str | None = None) -> dict:
    """Copia el workflow y aplica únicamente entradas declaradas previamente."""
    if fps <= 0 or fps > 60:
        raise ValueError("fps fuera de rango")
    width, height = dimensions(aspect_ratio, resolution)
    values: dict[str, Any] = {
        "positive_prompt": shot.prompt,
        "negative_prompt": shot.negative_prompt,
        "seed": shot.seed,
        "width": width,
        "height": height,
        "frames": int(math.ceil(shot.duration_seconds * fps)),
        "reference_image": reference_filename,
    }
    if "positive_prompt" not in bindings:
        raise ValueError("Sin binding para prompt positivo")
    output = copy.deepcopy(graph)
    for semantic, mapping in bindings.items():
        if semantic not in SEMANTIC_FIELDS:
            raise ValueError(f"Variable desconocida: {semantic}")
        node_id = str(mapping.get("node", ""))
        field_name = str(mapping.get("input", ""))
        if node_id not in output:
            raise ValueError(f"No existe nodo {node_id} para {semantic}")
        inputs = output[node_id].get("inputs")
        if not isinstance(inputs, dict) or field_name not in inputs:
            raise ValueError(f"No existe entrada {field_name} del nodo {node_id}")
        if semantic == "reference_image" and not reference_filename:
            raise ValueError("La escena no tiene imagen de referencia importada a ComfyUI")
        # No se sustituyen enlaces entre nodos accidentalmente.
        if isinstance(inputs[field_name], list):
            raise ValueError(f"Binding {semantic} apunta a enlace, no a parámetro literal")
        inputs[field_name] = values[semantic]
    return output


class ComfyClient:
    def __init__(self, endpoint: str = "http://127.0.0.1:8188",
                 timeout: float = 30.0):
        self.endpoint = local_url(endpoint)
        self.timeout = timeout

    def _request(self, method: str, route: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req = Request(self.endpoint + route, data=data, method=method,
                      headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def health(self) -> bool:
        try:
            self._request("GET", "/system_stats")
            return True
        except (OSError, ValueError):
            return False

    def queue(self, graph: dict) -> str:
        answer = self._request("POST", "/prompt",
                               {"prompt": graph, "client_id": str(uuid.uuid4())})
        if answer.get("node_errors"):
            raise RuntimeError(f"ComfyUI rechazó nodos: {answer['node_errors']}")
        prompt_id = answer.get("prompt_id")
        if not isinstance(prompt_id, str):
            raise RuntimeError("ComfyUI no devolvió prompt_id")
        return prompt_id

    def history(self, prompt_id: str) -> dict:
        if not prompt_id or not all(c.isalnum() or c in "-_" for c in prompt_id):
            raise ValueError("Identificador de tarea inválido")
        return self._request("GET", "/history/" + prompt_id)

    def wait(self, prompt_id: str, *, timeout: float = 3600, interval: float = 2.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            history = self.history(prompt_id)
            job = history.get(prompt_id)
            if job:
                status = job.get("status", {})
                if status.get("status_str") == "error" or status.get("completed") is False:
                    if status.get("status_str") == "error":
                        raise RuntimeError(f"ComfyUI devolvió error: {status}")
                if status.get("completed") is True or job.get("outputs"):
                    return job
            time.sleep(interval)
        raise TimeoutError(f"ComfyUI no completó el trabajo {prompt_id} en {timeout} s")

    def download_outputs(self, job: dict, folder: str | Path) -> list[Path]:
        outdir = Path(folder)
        outdir.mkdir(parents=True, exist_ok=True)
        results: list[Path] = []
        for node in job.get("outputs", {}).values():
            for field in ("images", "gifs", "videos"):
                for item in node.get(field, []):
                    filename = item.get("filename")
                    if not isinstance(filename, str) or not filename:
                        continue
                    if item.get("type", "output") != "output":
                        continue
                    safe_name = Path(filename).name
                    if safe_name != filename:
                        raise ValueError("Nombre inseguro en resultado de ComfyUI")
                    target = outdir / safe_name
                    if target.exists():
                        raise FileExistsError(f"Archivo de salida ya existe: {target}")
                    params = urlencode({"filename": filename,
                                        "subfolder": item.get("subfolder", ""),
                                        "type": "output"})
                    req = Request(self.endpoint + "/view?" + params)
                    with urlopen(req, timeout=self.timeout) as response, target.open("wb") as dest:
                        while True:
                            part = response.read(1024 * 1024)
                            if not part:
                                break
                            dest.write(part)
                    results.append(target)
        if not results:
            raise RuntimeError("El workflow terminó sin resultados descargables de imagen/video")
        return results
