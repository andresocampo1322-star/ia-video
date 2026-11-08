"""Regresión del banco de personajes sin red, cuotas ni GPU.

Respeta el estilo de los tests existentes: pytest, tmp_path y dobles mínimos.
"""
from __future__ import annotations

import json
import struct
import sys
import types
import zlib
from pathlib import Path

import pytest

from stickman.character_bank import (
    GeneradorSpaceHuggingFace,
    descripcion_personaje,
    generar_banco_personajes,
    referencias_de_escena,
)
from stickman.schema import CastMember, Preset, Script, validate_script


def _png_valido(ancho: int = 2, alto: int = 2) -> bytes:
    """Construye un PNG RGB válido, sin Pillow ni ninguna librería de imagen."""
    def bloque(tipo: bytes, datos: bytes) -> bytes:
        carga = tipo + datos
        return (struct.pack(">I", len(datos)) + carga +
                struct.pack(">I", zlib.crc32(carga) & 0xFFFFFFFF))
    cabecera = struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0)
    datos = b"".join(b"\x00" + b"\x20\x40\x60" * ancho for _ in range(alto))
    return (b"\x89PNG\r\n\x1a\n" + bloque(b"IHDR", cabecera) +
            bloque(b"IDAT", zlib.compress(datos)) + bloque(b"IEND", b""))


class GeneradorFalso:
    identificador = "prueba-sin-red"

    def __init__(self, contenido: bytes | None = None):
        self.llamadas: list[tuple[str, int]] = []
        self.contenido = contenido if contenido is not None else _png_valido()
        self.fallar = False

    def generar(self, descripcion: str, semilla: int) -> bytes:
        self.llamadas.append((descripcion, semilla))
        if self.fallar:
            raise RuntimeError("Servidor simulado indisponible")
        return self.contenido


def _guion():
    bruto = {
        "title": "Prueba de continuidad",
        "cast": [
            {"id": "nora", "name": "Nora",
             "preset": {"hair": "ponytail", "hair_color": "#22201E",
                        "accessory": "glasses", "color": "#2F6FB0"}},
            {"id": "leo", "name": "Leo",
             "preset": {"hair": "curly", "hair_color": "#964B00",
                        "accessory": "cap", "color": "#2E8B6A"}},
        ],
        "scenes": [
            {"narration": "Nora camina.", "characters": [{"id": "nora"}]},
            {"narration": "Nora habla con Leo.",
             "characters": [{"id": "nora"}, {"id": "leo"}]},
        ],
    }
    guion, avisos = validate_script(bruto)
    assert not avisos
    return guion


def test_descripcion_respeta_pelo_color_y_accesorio():
    descripcion = descripcion_personaje(_guion().cast[0])
    assert "Nora" in descripcion
    assert "cola de caballo" in descripcion
    assert "#22201E" in descripcion
    assert "#2F6FB0" in descripcion
    assert "gafas" in descripcion
    assert "una sola persona" in descripcion.lower()


def test_genera_una_vez_por_personaje_y_reutiliza_entre_escenas(tmp_path):
    guion = _guion()
    falso = GeneradorFalso()
    banco = generar_banco_personajes(guion, tmp_path, falso)
    assert set(banco) == {"nora", "leo"}
    assert len(falso.llamadas) == 2
    assert banco["nora"] == tmp_path / "personajes" / "nora.png"
    assert all(ruta.read_bytes() == _png_valido() for ruta in banco.values())
    assert all(ruta.with_suffix(".json").exists() for ruta in banco.values())

    # El segundo uso no debe llamar al proveedor ni cambiar los PNG.
    antes = {id_: ruta.stat().st_mtime_ns for id_, ruta in banco.items()}
    nuevo = generar_banco_personajes(guion, tmp_path, falso)
    assert nuevo == banco
    assert len(falso.llamadas) == 2
    assert antes == {id_: ruta.stat().st_mtime_ns for id_, ruta in nuevo.items()}
    assert referencias_de_escena(guion.scenes[0], banco) == {
        "nora": str(banco["nora"])
    }
    assert referencias_de_escena(guion.scenes[1], banco) == {
        "nora": str(banco["nora"]), "leo": str(banco["leo"])
    }


def test_cambio_de_apariencia_invalida_solo_la_referencia_afectada(tmp_path):
    guion = _guion()
    falso = GeneradorFalso()
    banco = generar_banco_personajes(guion, tmp_path, falso)
    metadata_antes = json.loads(banco["nora"].with_suffix(".json").read_text())
    leo_antes = banco["leo"].stat().st_mtime_ns
    guion_modificado = guion.model_copy(deep=True)
    guion_modificado.cast[0].preset.hair = "short"
    guion_modificado.cast[0].preset.color = "#D24D1E"
    generar_banco_personajes(guion_modificado, tmp_path, falso)
    assert len(falso.llamadas) == 3
    assert "pelo corto" in falso.llamadas[-1][0]
    assert banco["leo"].stat().st_mtime_ns == leo_antes
    metadata_despues = json.loads(banco["nora"].with_suffix(".json").read_text())
    assert metadata_antes["huella"] != metadata_despues["huella"]


def test_fallo_no_sobrescribe_imagen_previa(tmp_path):
    guion = _guion()
    falso = GeneradorFalso()
    banco = generar_banco_personajes(guion, tmp_path, falso)
    original = banco["nora"].read_bytes()
    dato_original = banco["nora"].with_suffix(".json").read_bytes()
    falso.fallar = True
    with pytest.raises(RuntimeError, match="indisponible"):
        generar_banco_personajes(guion, tmp_path, falso, forzar=True)
    assert banco["nora"].read_bytes() == original
    assert banco["nora"].with_suffix(".json").read_bytes() == dato_original
    assert not list((tmp_path / "personajes").glob("*.lock"))


def test_png_manual_sin_metadata_no_se_sobrescribe(tmp_path):
    carpeta = tmp_path / "personajes"
    carpeta.mkdir()
    imagen = carpeta / "nora.png"
    imagen.write_bytes(_png_valido())
    falso = GeneradorFalso()
    solo_nora = _guion().model_copy(deep=True)
    solo_nora.cast = solo_nora.cast[:1]
    banco = generar_banco_personajes(solo_nora, tmp_path, falso)
    assert banco["nora"] == imagen
    assert falso.llamadas == []


def test_referencias_solo_actores_en_plano_y_error_si_falta(tmp_path):
    guion = _guion()
    banco = generar_banco_personajes(guion, tmp_path, GeneradorFalso())
    assert list(referencias_de_escena(guion.scenes[0], banco)) == ["nora"]
    with pytest.raises(KeyError, match="leo"):
        referencias_de_escena(guion.scenes[1], {"nora": banco["nora"]})


def test_cast_vacio_no_crea_carpeta_ni_usa_red(tmp_path):
    guion = _guion().model_copy(deep=True)
    guion.cast = []
    falso = GeneradorFalso()
    assert generar_banco_personajes(guion, tmp_path, falso) == {}
    assert not (tmp_path / "personajes").exists()


def test_proveedor_sdxl_y_flux_usando_cliente_gradio_simulado(monkeypatch):
    observaciones = []

    class ClienteFalso:
        def __init__(self, espacio, **opciones):
            observaciones.append(("conexion", espacio, opciones))

        def predict(self, *args, **kwargs):
            observaciones.append(("predict", args, kwargs))
            return ("/tmp/imagen_generada.png", 123)

    monkeypatch.setitem(sys.modules, "gradio_client",
                        types.SimpleNamespace(Client=ClienteFalso))
    mono = GeneradorSpaceHuggingFace("sdxl")
    assert mono.generar("Nora con lentes", 123) == "/tmp/imagen_generada.png"
    assert observaciones[0][1] == "hysts/SDXL"
    assert observaciones[1][2]["api_name"] == "/predict"
    assert observaciones[1][1][7] == 123
    observaciones.clear()
    flux = GeneradorSpaceHuggingFace("flux_schnell")
    assert flux.generar("Nora con lentes", 123) == "/tmp/imagen_generada.png"
    assert observaciones[0][1] == "black-forest-labs/FLUX.1-schnell"
    assert observaciones[1][2]["api_name"] == "/infer"
    assert observaciones[1][1][2] is False


def test_errores_de_png_no_se_guardan_como_imagen_valida(tmp_path):
    falso = GeneradorFalso(b"no es un archivo png")
    with pytest.raises((ValueError, RuntimeError)):
        generar_banco_personajes(_guion(), tmp_path, falso)
    assert not (tmp_path / "personajes" / "nora.png").exists()
