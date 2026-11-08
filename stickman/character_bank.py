"""Banco de imágenes maestras para el reparto de Stickman IA.

Genera una única referencia por identidad y aspecto y la reutiliza entre escenas.
No modifica el motor clásico ni impone un generador concreto. Hugging Face
Gradio es opcional y solo se importa si se solicita una generación real.

Las imágenes de referencia no garantizan, por sí solas, fidelidad facial en un
modelo de video: el backend debe aceptar y utilizar esas imágenes.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Mapping, Protocol

from .schema import CastMember, Scene, Script

FIRMA_PNG = b"\x89PNG\r\n\x1a\n"

PEINADOS = {
    "none": "sin pelo, cabeza rapada",
    "short": "pelo corto",
    "long": "pelo largo",
    "bun": "pelo recogido en un moño",
    "ponytail": "pelo recogido en una cola de caballo",
    "curly": "pelo rizado",
    "spiky": "pelo de puntas",
}

ACCESORIOS = {
    "none": "",
    "glasses": "gafas",
    "cap": "gorra",
    "headphones": "auriculares",
    "tie": "corbata",
    "bow": "lazo",
}


class GeneradorImagen(Protocol):
    """Contrato mínimo para sustituir el proveedor sin modificar el banco."""

    def generar(self, descripcion: str, semilla: int) -> str | Path | bytes:
        """Entrega una imagen PNG/JPG/WEBP o una ruta local al archivo."""


class GeneradorSpaceHuggingFace:
    """Generación remota con un Space público sin GPU propia.

    El uso gratuito depende de la cuota, disponibilidad y condiciones del
    propietario del Space; la interfaz no garantiza servicio sin coste.
    """

    ESPACIOS = {
        "sdxl": "hysts/SDXL",
        "flux_schnell": "black-forest-labs/FLUX.1-schnell",
    }

    def __init__(self, modelo: str = "sdxl", *, token: str | None = None):
        if modelo not in self.ESPACIOS:
            raise ValueError("Modelo no admitido: usa 'sdxl' o 'flux_schnell'")
        self.modelo = modelo
        self.token = token

    def generar(self, descripcion: str, semilla: int) -> str | Path | bytes:
        try:
            from gradio_client import Client
        except ImportError as error:
            raise RuntimeError(
                "Para generar imágenes remotas instala: pip install gradio_client Pillow"
            ) from error
        opciones = {}
        token = self.token or os.getenv("HF_TOKEN")
        if token:
            opciones["token"] = token
        try:
            cliente = Client(self.ESPACIOS[self.modelo], **opciones)
            if self.modelo == "flux_schnell":
                # Firma del Space oficial: prompt, seed, aleatorio, ancho,
                # alto y pasos. El endpoint infer puede variar si se actualiza.
                respuesta = cliente.predict(
                    descripcion, int(semilla), False, 1024, 1024, 4,
                    api_name="/infer"
                )
            else:
                # Firma publicada por hysts/SDXL (generación base sin refiner).
                respuesta = cliente.predict(
                    descripcion, "", "", "", False, False, False,
                    int(semilla), 1024, 1024, 5.0, 5.0, 25, 25, False,
                    api_name="/predict"
                )
        except Exception as error:
            raise RuntimeError(
                f"No se pudo generar la referencia en "
                f"{self.ESPACIOS[self.modelo]}. Comprueba el Space, su API, "
                "la cuota gratuita y la conexión."
            ) from error
        # Gradio puede devolver (ruta, semilla), una ruta o un diccionario
        # con 'path' según la versión del componente Image.
        imagen = respuesta[0] if isinstance(respuesta, (tuple, list)) else respuesta
        if isinstance(imagen, dict):
            imagen = imagen.get("path") or imagen.get("name")
        if not isinstance(imagen, (str, Path)):
            raise RuntimeError(
                "El Space cambió el formato de respuesta: no devolvió imagen local"
            )
        return imagen


def descripcion_personaje(personaje: CastMember) -> str:
    """Construye la descripción a partir del reparto VALIDADO, sin inventar rasgos."""
    apariencia = personaje.preset
    rasgos = PEINADOS[apariencia.hair]
    accesorio = ACCESORIOS[apariencia.accessory]
    nombre = personaje.name.strip() or personaje.id
    partes = [
        "Hoja maestra de diseño de personaje para animación 2D de alta calidad",
        f"Personaje: {nombre}",
        f"Cabello: {rasgos}; color de cabello {apariencia.hair_color}",
        f"Color predominante de la ropa: {apariencia.color}",
    ]
    if accesorio:
        partes.append(f"Accesorio constante: {accesorio}")
    partes.extend([
        "Una sola persona, cuerpo entero y rostro claramente visible",
        "Pose de pie neutra, vista frontal, proporciones coherentes",
        "Fondo sencillo, líneas limpias, detalles nítidos, sin textos",
        "Mantener exactamente el mismo diseño en todas las escenas",
    ])
    return ". ".join(partes) + "."


def _huella(personaje: CastMember, modelo: str) -> str:
    contenido = {
        "version": 1,
        "modelo": modelo,
        "personaje": personaje.model_dump(mode="json"),
        "descripcion": descripcion_personaje(personaje),
    }
    datos = json.dumps(contenido, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(datos).hexdigest()


def _semilla(huella: str) -> int:
    return int(huella[:8], 16) % 2147483647


def _es_png_valido(ruta: Path) -> bool:
    if not ruta.is_file() or ruta.stat().st_size < 45:
        return False
    with ruta.open("rb") as archivo:
        inicio = archivo.read(24)
    if not inicio.startswith(FIRMA_PNG) or inicio[12:16] != b"IHDR":
        return False
    ancho = int.from_bytes(inicio[16:20], "big")
    alto = int.from_bytes(inicio[20:24], "big")
    return 0 < ancho <= 8192 and 0 < alto <= 8192


def _guardar_como_png(imagen: str | Path | bytes, destino: Path) -> None:
    """Copia PNG o convierte otra imagen con Pillow, si está disponible."""
    if isinstance(imagen, bytes):
        destino.write_bytes(imagen)
    else:
        origen = Path(imagen)
        if not origen.is_file():
            raise FileNotFoundError("El Space no devolvió un archivo de imagen local")
        if origen.resolve() != destino.resolve():
            shutil.copyfile(origen, destino)
    if _es_png_valido(destino):
        return
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError(
            "La imagen no es PNG. Instala Pillow para convertir JPG/WEBP."
        ) from error
    try:
        with Image.open(destino) as abierta:
            if abierta.width > 8192 or abierta.height > 8192:
                raise ValueError("La imagen supera las dimensiones admitidas")
            imagen_rgb = abierta.convert("RGB")
            imagen_rgb.save(destino, format="PNG")
    except Exception as error:
        raise ValueError("El proveedor devolvió una imagen inválida") from error
    if not _es_png_valido(destino):
        raise ValueError("No se pudo guardar una imagen PNG válida")


@contextmanager
def _bloqueo(ruta: Path, *, espera: float = 60.0):
    """Evita generar dos veces el mismo personaje en procesos simultáneos."""
    inicio = time.monotonic()
    while True:
        try:
            descriptor = os.open(str(ruta), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            break
        except FileExistsError:
            if time.monotonic() - inicio > espera:
                raise TimeoutError(f"La referencia sigue bloqueada: {ruta.name}")
            time.sleep(0.10)
    try:
        yield
    finally:
        ruta.unlink(missing_ok=True)


def generar_banco_personajes(
    guion: Script,
    carpeta_salida: str | Path,
    generador: GeneradorImagen | None = None,
    *,
    modelo: str = "sdxl",
    forzar: bool = False,
) -> dict[str, Path]:
    """Genera/reutiliza salida/personajes/<id>.png una vez por identidad y aspecto.

    * No hay llamadas externas si todas las referencias están en caché.
    * Si cambia el preset/nombre/modelo, se crea otra referencia y se actualiza
      el mismo archivo de identidad (por eso no hay mezcla de apariencias).
    * Un PNG sin metadatos se considera imagen aportada manualmente; no se
      sobrescribe salvo que el usuario indique forzar=True.
    * En caso de error, conserva la referencia anterior.
    """
    carpeta = Path(carpeta_salida) / "personajes"
    if not guion.cast:
        return {}
    carpeta.mkdir(parents=True, exist_ok=True)
    proveedor = generador
    nombre_modelo = (modelo if proveedor is None else
                     getattr(proveedor, "identificador", proveedor.__class__.__name__))
    resultado: dict[str, Path] = {}
    identificadores: set[str] = set()
    for personaje in guion.cast:
        if personaje.id in identificadores:
            raise ValueError(f"ID duplicado en el reparto: {personaje.id}")
        identificadores.add(personaje.id)
        imagen = carpeta / f"{personaje.id}.png"
        metadatos = carpeta / f"{personaje.id}.json"
        bloqueo = carpeta / f".{personaje.id}.lock"
        huella = _huella(personaje, str(nombre_modelo))
        with _bloqueo(bloqueo):
            anterior = {}
            if metadatos.is_file():
                try:
                    anterior = json.loads(metadatos.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    anterior = {}
            valida = _es_png_valido(imagen)
            if valida and not forzar and (not anterior or anterior.get("huella") == huella):
                resultado[personaje.id] = imagen
                continue
            if proveedor is None:
                proveedor = GeneradorSpaceHuggingFace(modelo=modelo)
            with tempfile.TemporaryDirectory(dir=carpeta, prefix=".referencia_") as temporal:
                provisional = Path(temporal) / "nueva.png"
                generada = proveedor.generar(
                    descripcion_personaje(personaje), _semilla(huella))
                _guardar_como_png(generada, provisional)
                informacion = {
                    "id": personaje.id,
                    "huella": huella,
                    "modelo": str(nombre_modelo),
                    "semilla": _semilla(huella),
                    "descripcion": descripcion_personaje(personaje),
                }
                meta_temporal = Path(temporal) / "datos.json"
                meta_temporal.write_text(
                    json.dumps(informacion, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                os.replace(provisional, imagen)
                os.replace(meta_temporal, metadatos)
            resultado[personaje.id] = imagen
    return resultado


def referencias_de_escena(
    escena: Scene,
    banco: Mapping[str, str | Path],
) -> dict[str, str]:
    """Asocia SOLO los actores presentes; lista para ScenePrompt cuando exista.

    No importa ai_backend.py ni presupone cómo Claude definió ScenePrompt.
    """
    referencias: dict[str, str] = {}
    for personaje in escena.characters:
        if personaje.id not in banco:
            raise KeyError(f"No hay imagen maestra para {personaje.id}")
        referencias[personaje.id] = str(Path(banco[personaje.id]))
    return referencias
