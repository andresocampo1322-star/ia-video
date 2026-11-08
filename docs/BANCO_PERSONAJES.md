# Banco de personajes — integración incremental con Stickman IA

## Objetivo

Crear una imagen de referencia por integrante del reparto Script.cast,
reutilizar exactamente el mismo PNG en cada plano y no consumir cuota de
generación cada vez que reaparezca el personaje.

Esta PR no modifica render.py ni sustituye el motor original.

## Investigación Hugging Face (noviembre de 2026)

FLUX.1-schnell: https://huggingface.co/black-forest-labs/FLUX.1-schnell

- Modelo de 12B parámetros, Apache 2.0, buen seguimiento de descripciones,
  generación con pocas iteraciones.
- Space oficial: https://huggingface.co/spaces/black-forest-labs/FLUX.1-schnell
- La consulta de parámetros del Space oficial devolvió 404 durante esta
  revisión: disponibilidad de API, cuota y ejecución NO confirmadas.
- Disponible como opción experimental modelo="flux_schnell"; el endpoint
  infer está basado en el app.py público y puede cambiar.

SDXL base 1.0: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0

- Licencia CreativeML OpenRAIL++-M, modelo abierto.
- Space: https://huggingface.co/spaces/hysts/SDXL
- El archivo app.py del Space expone endpoint predict y el orden de los
  parámetros de generación. Elegido como opción inicial modelo="sdxl".
- La ejecución depende de disponibilidad y cuotas ZeroGPU: no se promete
  GPU gratuita ilimitada ni disponibilidad permanente.

Documentación: https://huggingface.co/docs/hub/en/spaces-api-endpoints
Cuotas: https://huggingface.co/docs/hub/en/spaces-zerogpu

Esta PR NO ejecutó generación real. Las pruebas se realizaron sin red.

## Preparación y uso

Solo cuando se quiera generar imágenes remotas:

    python -m pip install gradio_client Pillow

El token es opcional y se toma de la variable de entorno HF_TOKEN; no se
debe almacenar en los archivos ni subir al repositorio.

Ejemplo desde la carpeta raíz del proyecto:

    from stickman.schema import load_script
    from stickman.character_bank import generar_banco_personajes, referencias_de_escena

    guion, avisos = load_script("guion.json")
    banco = generar_banco_personajes(guion, "salida", modelo="sdxl")
    banco = generar_banco_personajes(guion, "salida", modelo="sdxl")
    rutas_del_plano = referencias_de_escena(guion.scenes[0], banco)

Se crean salida/personajes/nora.png y salida/personajes/nora.json, etc.
El JSON registra huella de identidad, nombre, preset y proveedor.
El segundo uso de la misma referencia no consulta el servidor.

Si cambian cabello, color, accesorio, nombre o proveedor, se detecta
la diferencia y se regenera solo el personaje cambiado.
Una imagen manual sin metadatos se respeta; forzar=True obliga a renovar.

Campos aprovechados del schema original: hair, hair_color, accessory,
color (principal de ropa/cuerpo). No se inventan atributos no definidos.

## Integración pendiente con la arquitectura de Claude

Al revisar todas las ramas publicadas, incluidas main y
feat/studio-pro-motor-original-sin-comfy-v8, NO aparecieron:

- stickman/ai_backend.py, con VideoBackend/MockBackend/ColabBackend/ScenePrompt
- stickman/render_ai.py, con AIVideoRenderer
- tests/test_render_ai.py
- documento de arquitectura acordado

Se ha respetado la instrucción de NO recrear ni reescribir estos módulos.

El banco deja lista una asignación estable de referencias por personaje
para cada plano, usando referencias_de_escena(escena, banco).

Claude debe publicar los módulos y verificar entonces:
1) Campo opcional referencias_personajes con valor por defecto vacío
   en la definición REAL de ScenePrompt, conservando su firma anterior.
2) Vinculación desde el punto REAL de creación de ScenePrompt en
   AIVideoRenderer, sin imponer rutas cuando no se use banco.
3) Pruebas originales de MockBackend y ColabBackend con y sin referencias.

No sería seguro inventar firmas de esos módulos sin leer el código.

## Pruebas

    python -m pytest -q tests/test_character_bank.py

Los nueve casos verifican la descripción del preset, generación única,
reutilización exacta, cambio de apariencia, preservación ante errores,
imagen aportada manualmente, reparto vacío, selección de actores por
escena y contrato Gradio simulado. No requieren red, GPU ni créditos.

La persistencia del PNG NO obliga al modelo de video a respetar la cara
o vestuario; para eso el backend de video necesita condicionamiento visual.
